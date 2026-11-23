"""Vault health report (product_backend.md section 6.5): integrity, master key strength, weak,
reused, breached and rotation checks, combined into one score.

The report only ever contains entry ids and site names, never a password."""

import math
from collections import defaultdict
from datetime import timedelta

from sqlalchemy.orm import Session

from app.controllers import entries as entry_logic
from app.controllers import security as sec
from app.core import passwords
from app.core.crypto import IntegrityError
from app.db import iso, utcnow
from app.dependencies import Unlocked
from app.services import hibp

WEIGHTS = {
    "integrity": 25,
    "master_key": 15,
    "weak": 20,
    "reused": 15,
    "breached": 15,
    "rotation": 10,
}
INTEGRITY_CAP = 40  # any tampered entry keeps the score in the red
ARGON2_GUESSES_PER_SECOND = 1e4  # the same attacker-rig assumption as the signup meter
SECONDS_PER_YEAR = 31_557_600
TIME_STEPS = (
    (60, "second", 1),
    (3600, "minute", 60),
    (86400, "hour", 3600),
    (SECONDS_PER_YEAR, "day", 86400),
)


def band_for(metric: int | None) -> str:
    """The 5-band scale shared with the UI (design.md section 1.1)."""
    if metric is None:
        return "unavailable"
    for floor, name in ((90, "excellent"), (75, "good"), (60, "fair"), (40, "poor")):
        if metric >= floor:
            return name
    return "critical"


def compute_score(metrics: dict[str, int | None], integrity_failed: bool) -> int:
    """Weighted average of the available metrics (an unavailable check drops out and the rest
    are renormalized); any integrity failure caps the result at 40."""
    available = {k: m for k, m in metrics.items() if m is not None}
    total_weight = sum(WEIGHTS[k] for k in available)
    score = round(sum(WEIGHTS[k] * m for k, m in available.items()) / total_weight)
    return min(score, INTEGRITY_CAP) if integrity_failed else score


def _percent(good: int, total: int) -> int:
    return 100 if total == 0 else round(100 * good / total)


def crack_time_text(guesses_log10: float) -> str:
    """Average time to crack with Argon2id: half the guesses at the attacker's rate."""
    log10_seconds = guesses_log10 - math.log10(2 * ARGON2_GUESSES_PER_SECOND)
    if log10_seconds < 0:
        return "under a second"
    years_log10 = log10_seconds - math.log10(SECONDS_PER_YEAR)
    if years_log10 >= 12:
        return f"~10^{round(years_log10)} years"
    seconds = 10**log10_seconds
    for limit, unit, size in TIME_STEPS:
        if seconds < limit:
            n = max(1, round(seconds / size))
            return f"~{n} {unit}{'' if n == 1 else 's'}"
    years = 10**years_log10
    for size, word in ((1e9, "billion"), (1e6, "million")):
        if years >= size:
            return f"~{years / size:.0f} {word} years"
    return f"~{round(years):,} years"


def _ref(entry) -> dict:
    return {"id": entry.id, "site_name": entry.site_name}


def build_report(db: Session, unlocked: Unlocked, ip: str | None) -> dict:
    rows = db.scalars(entry_logic.owned_entries(unlocked.user.id)).all()
    total = len(rows)

    failed, readable = [], []  # readable: (entry, decrypted fields)
    for entry in rows:
        try:
            readable.append((entry, entry_logic.decrypted(unlocked, entry)))
        except IntegrityError:
            failed.append(entry)
    if failed:
        sec.record_event(db, unlocked.user.id, "tamper_detected", ip)
        db.commit()

    # weak: zxcvbn score below 3
    weak = []
    for entry, fields in readable:
        score, _ = passwords.strength(
            fields["password"], [entry.site_name, fields["username"] or ""]
        )
        if score < 3:
            weak.append({**_ref(entry), "zxcvbn_score": score})

    # reused: the same password in more than one entry
    by_password = defaultdict(list)
    for entry, fields in readable:
        by_password[fields["password"]].append(entry)
    groups = [[_ref(e) for e in members] for members in by_password.values() if len(members) > 1]
    reused_count = sum(len(g) for g in groups)

    # breached: HIBP k-anonymity, results cached in memory for this session
    counts = hibp.breach_counts(
        {entry.id: fields["password"] for entry, fields in readable}, unlocked.vault.hibp_cache
    )
    breached = None
    if counts is not None:
        breached = [
            {**_ref(entry), "count": counts[entry.id]}
            for entry, _ in readable
            if counts[entry.id] > 0
        ]

    # rotation: entries with a reminder whose password is older than the interval
    now = utcnow()
    tracked = [e for e in rows if e.rotation_days]
    due = []
    for entry in tracked:
        overdue = (now - entry.password_changed_at) - timedelta(days=entry.rotation_days)
        if overdue > timedelta(0):
            due.append({**_ref(entry), "days_overdue": overdue.days})

    guesses_log10 = unlocked.vault.guesses_log10
    metrics = {
        # Any tampered entry makes this critical: 11 of 12 verified must not read "Excellent".
        "integrity": min(_percent(total - len(failed), total), INTEGRITY_CAP - 1)
        if failed
        else 100,
        "master_key": None if guesses_log10 is None else min(100, round(guesses_log10 * 5)),
        "weak": _percent(total - len(weak), total),
        "reused": _percent(total - reused_count, total),
        "breached": None if breached is None else _percent(total - len(breached), total),
        "rotation": _percent(len(tracked) - len(due), len(tracked)),
    }
    score = compute_score(metrics, integrity_failed=bool(failed))

    def check(name: str, **extra) -> dict:
        return {"metric": metrics[name], "band": band_for(metrics[name]), **extra}

    master_extra = (
        {}
        if guesses_log10 is None
        else {
            "guesses_log10": round(guesses_log10, 1),
            "crack_time_argon2": crack_time_text(guesses_log10),
        }
    )
    return {
        "score": score,
        "band": band_for(score),
        "checks": {
            "integrity": check("integrity", failed=[_ref(e) for e in failed]),
            "master_key": check("master_key", **master_extra),
            "weak": check("weak", entries=weak),
            "reused": check("reused", groups=groups),
            "breached": check("breached", entries=breached or []),
            "rotation": check("rotation", due=due, tracked=len(tracked)),
        },
        "entry_count": total,
        "checked_at": iso(now),
    }
