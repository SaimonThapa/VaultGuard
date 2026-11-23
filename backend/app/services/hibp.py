"""Have I Been Pwned "range" lookups (k-anonymity): only the first 5 characters of a password's
SHA-1 ever leave this server, never the password or the full hash.

Standard library only. Any network problem means "unavailable", never an error for the user."""

import hashlib
import logging
import urllib.request

from app import config

logger = logging.getLogger("vaultguard")
RANGE_URL = "https://api.pwnedpasswords.com/range/"


def fetch_range(prefix: str) -> str:
    """Raw response body for a 5-character prefix. Padded, so response size reveals nothing."""
    request = urllib.request.Request(  # noqa: S310  (constant https URL)
        RANGE_URL + prefix,
        headers={"Add-Padding": "true", "User-Agent": "VaultGuard-student-project"},
    )
    with urllib.request.urlopen(request, timeout=config.HIBP_TIMEOUT_SECONDS) as response:  # noqa: S310  # nosec B310
        return response.read().decode("ascii")


def _parse(body: str) -> dict[str, int]:
    found = {}
    for line in body.splitlines():
        suffix, _, count = line.strip().partition(":")
        if suffix and count.isdigit() and int(count) > 0:  # padding rows have a count of 0
            found[suffix.upper()] = int(count)
    return found


def breach_counts(
    passwords: dict[str, str], cache: dict[str, dict[str, int]]
) -> dict[str, int] | None:
    """Map each entry id to how many times its password appears in known breaches (0 = none).
    Returns None when the check can't run (disabled, offline, timeout). `cache` maps a prefix to
    its parsed result for the life of the session, so repeat checkups don't hit the network."""
    if not config.HIBP_ENABLED:
        return None
    counts = {}
    try:
        for entry_id, password in passwords.items():
            digest = hashlib.sha1(password.encode(), usedforsecurity=False).hexdigest().upper()  # noqa: S324
            prefix, suffix = digest[:5], digest[5:]
            if prefix not in cache:
                cache[prefix] = _parse(fetch_range(prefix))
            counts[entry_id] = cache[prefix].get(suffix, 0)
    except Exception:  # offline, timeout, bad response: the checkup still works without HIBP
        logger.warning("HIBP check unavailable")
        return None
    return counts
