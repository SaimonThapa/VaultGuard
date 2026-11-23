import {
	ArrowDownToLine,
	ArrowUpFromLine,
	CircleCheck,
	KeyRound,
	LogIn,
	ShieldAlert,
	TriangleAlert,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Button from "../components/Button.jsx";
import { api } from "../lib/api.js";
import { dayLabel } from "../lib/format.js";

// type -> [text, icon, tone, chips]. Unknown types fall back to their raw name (never breaks).
const EVENTS = {
	login_ok: ["Signed in", LogIn, "plain", ["signins"]],
	login_failed: ["Failed sign-in attempt", TriangleAlert, "warn", ["signins"]],
	login_locked: [
		"Sign-in locked after repeated failures",
		ShieldAlert,
		"alert",
		["signins", "alerts"],
	],
	password_changed: [
		"Account password changed",
		KeyRound,
		"plain",
		["signins"],
	],
	refresh_reuse: [
		"Reused session token blocked; session ended",
		ShieldAlert,
		"alert",
		["signins", "alerts"],
	],
	unlock_ok: ["Vault unlocked", CircleCheck, "plain", ["vault"]],
	unlock_failed: ["Failed unlock attempt", TriangleAlert, "warn", ["vault"]],
	unlock_locked: [
		"Unlock locked after repeated failures",
		ShieldAlert,
		"alert",
		["vault", "alerts"],
	],
	tamper_detected: [
		"Tampering detected on stored data",
		ShieldAlert,
		"alert",
		["vault", "alerts"],
	],
	master_key_changed: [
		"Master key changed, vault re-encrypted",
		KeyRound,
		"plain",
		["vault"],
	],
	master_key_recovered: [
		"Master key reset with recovery key",
		KeyRound,
		"plain",
		["vault"],
	],
	vault_reset: [
		"Vault reset, all entries deleted",
		ShieldAlert,
		"alert",
		["vault", "alerts"],
	],
	import: ["Passwords imported", ArrowUpFromLine, "plain", ["vault"]],
	export: ["Encrypted backup exported", ArrowDownToLine, "plain", ["vault"]],
};
const TONE = { plain: "text-ink-2", warn: "text-warn", alert: "text-danger" };
const CHIPS = [
	["all", "All"],
	["signins", "Sign-ins"],
	["vault", "Vault"],
	["alerts", "Alerts"],
];

const clockTime = (iso) =>
	new Date(iso).toLocaleTimeString([], {
		hour: "2-digit",
		minute: "2-digit",
		hour12: false,
	});

export default function Activity() {
	const [events, setEvents] = useState(null);
	const [error, setError] = useState(false);
	const [chip, setChip] = useState("all");

	const load = useCallback(async () => {
		setError(false);
		try {
			setEvents(
				(await api("/api/account/activity?limit=100", { toast: false })).events,
			);
		} catch (err) {
			if (err.status !== 401) setError(true);
		}
	}, []);
	useEffect(() => {
		load();
	}, [load]);

	const shown = (events ?? []).filter(
		(e) => chip === "all" || (EVENTS[e.type]?.[3] ?? []).includes(chip),
	);
	const groups = [];
	for (const event of shown) {
		const label = dayLabel(event.created_at);
		if (groups.at(-1)?.label !== label) groups.push({ label, items: [] });
		groups.at(-1).items.push(event);
	}

	return (
		<div className="mx-auto max-w-3xl">
			<h1 className="text-2xl font-semibold">Activity log</h1>
			<p className="mb-5 text-ink-2">
				Security events on your account. Secrets are never recorded.
			</p>

			<div className="mb-4 flex flex-wrap items-center justify-between gap-2">
				<fieldset className="flex flex-wrap gap-2">
					<legend className="sr-only">Filter events</legend>
					{CHIPS.map(([key, label]) => (
						<button
							key={key}
							type="button"
							onClick={() => setChip(key)}
							aria-pressed={chip === key}
							className={`min-h-8 rounded-full px-3.5 text-sm font-medium ${
								chip === key
									? "bg-ink text-white"
									: "bg-black/[0.06] text-ink hover:bg-black/10"
							}`}
						>
							{label}
						</button>
					))}
				</fieldset>
				<span className="text-sm text-ink-2">Showing latest 100</span>
			</div>

			{error ? (
				<div className="rounded-[var(--radius-card)] border border-hairline bg-surface p-6 text-center">
					<p className="mb-3">Couldn't load activity.</p>
					<Button variant="secondary" onClick={load}>
						Retry
					</Button>
				</div>
			) : events === null ? (
				<ul
					className="space-y-2"
					aria-busy="true"
					aria-label="Loading activity"
				>
					{["a", "b", "c", "d", "e"].map((id) => (
						<li
							key={id}
							className="h-12 animate-pulse rounded-[var(--radius-control)] bg-black/[0.06]"
						/>
					))}
				</ul>
			) : shown.length === 0 ? (
				<p className="rounded-[var(--radius-card)] border border-hairline bg-surface p-6 text-center text-ink-2">
					No events here yet.
				</p>
			) : (
				groups.map(({ label, items }) => (
					<section key={label} className="mb-5">
						<h2 className="mb-2 px-1 text-sm font-medium text-ink-2">
							{label}
						</h2>
						<ul className="divide-y divide-hairline overflow-hidden rounded-[var(--radius-card)] border border-hairline bg-surface shadow-[var(--shadow-card)]">
							{items.map((event, index) => {
								const [text, Icon, tone] = EVENTS[event.type] ?? [
									event.type,
									CircleCheck,
									"plain",
									[],
								];
								return (
									<li
										// biome-ignore lint/suspicious/noArrayIndexKey: events have no id in the API
										key={`${event.created_at}-${index}`}
										className={`flex items-center gap-3 px-4 py-3 ${tone === "alert" ? "bg-danger-bg" : ""}`}
									>
										<Icon
											className={`size-5 shrink-0 ${TONE[tone]}`}
											aria-hidden
										/>
										<span className="min-w-0 flex-1 text-sm">{text}</span>
										<span className="hidden text-sm text-ink-3 sm:inline">
											{event.ip}
										</span>
										<span className="text-sm text-ink-2 tabular-nums">
											{clockTime(event.created_at)}
										</span>
									</li>
								);
							})}
						</ul>
					</section>
				))
			)}
		</div>
	);
}
