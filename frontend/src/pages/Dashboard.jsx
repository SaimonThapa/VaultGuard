import {
	Bug,
	Copy,
	KeyRound,
	RefreshCw,
	ShieldAlert,
	ShieldCheck,
	Timer,
	TriangleAlert,
} from "lucide-react";
import { Link, useNavigate } from "react-router";
import Button from "../components/Button.jsx";
import CheckRow from "../components/dashboard/CheckRow.jsx";
import HealthGauge from "../components/dashboard/HealthGauge.jsx";
import RadialRings from "../components/dashboard/RadialRings.jsx";
import StateOverlay from "../components/StateOverlay.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useHealth } from "../context/HealthContext.jsx";
import { useUnlockModal } from "../context/UnlockModalContext.jsx";
import { superscriptPowers, timeAgo } from "../lib/format.js";

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

// One-line finding + Review link for each of the six checkers (design.md §3.4).
function rowsFor(report) {
	const c = report?.checks;
	const count = report?.entry_count ?? 0;
	if (!c) {
		return [
			["integrity", ShieldCheck, "Integrity"],
			["master_key", KeyRound, "Crack resistance"],
			["weak", TriangleAlert, "Weak passwords"],
			["reused", Copy, "Reused passwords"],
			["breached", Bug, "Breached"],
			["rotation", Timer, "Rotation"],
		].map(([key, icon, name]) => ({
			key,
			icon,
			name,
			finding: "—",
			metric: null,
		}));
	}
	const failed = c.integrity.failed.length;
	const firstDue = c.rotation.due[0];
	return [
		{
			key: "integrity",
			icon: ShieldCheck,
			name: "Integrity",
			metric: c.integrity.metric,
			finding: failed
				? `${plural(failed, "entry")} failed (${c.integrity.failed.map((f) => f.site_name).join(", ")}). Possible tampering`
				: "All entries verified",
			review: failed ? "/passwords?filter=tampered" : null,
		},
		{
			key: "master_key",
			icon: KeyRound,
			name: "Crack resistance",
			metric: c.master_key.metric,
			finding: c.master_key.crack_time_argon2
				? `Master key: ${superscriptPowers(c.master_key.crack_time_argon2)} to crack with Argon2id`
				: "Master key strength unknown until your next unlock",
			review:
				c.master_key.metric != null && c.master_key.metric < 90
					? "/settings"
					: null,
		},
		{
			key: "weak",
			icon: TriangleAlert,
			name: "Weak passwords",
			metric: c.weak.metric,
			finding: c.weak.entries.length
				? `${c.weak.entries.length} of ${count} are weak`
				: "No weak passwords",
			review: c.weak.entries.length ? "/passwords?filter=weak" : null,
		},
		{
			key: "reused",
			icon: Copy,
			name: "Reused passwords",
			metric: c.reused.metric,
			finding: c.reused.groups.length
				? `${plural(c.reused.groups.length, "password")} used on multiple sites`
				: "No reused passwords",
			review: c.reused.groups.length ? "/passwords?filter=reused" : null,
		},
		{
			key: "breached",
			icon: Bug,
			name: "Breached",
			metric: c.breached.metric,
			finding:
				c.breached.metric == null
					? "Unavailable (offline)"
					: c.breached.entries.length
						? `${c.breached.entries.length} found in known breaches`
						: "None found in known breaches",
			review: c.breached.entries.length ? "/passwords?filter=breached" : null,
		},
		{
			key: "rotation",
			icon: Timer,
			name: "Rotation",
			metric: c.rotation.metric,
			finding: firstDue
				? `${c.rotation.due.length} overdue (${firstDue.site_name}, ${plural(firstDue.days_overdue, "day")})`
				: c.rotation.tracked
					? "All up to date"
					: "No rotation reminders set",
			review: firstDue ? "/passwords?filter=rotation" : null,
		},
	];
}

function Card({ title, children, className = "" }) {
	return (
		<section
			className={`rounded-[var(--radius-card)] border border-hairline bg-surface p-5 shadow-[var(--shadow-card)] ${className}`}
		>
			<h2 className="mb-3 font-medium">{title}</h2>
			{children}
		</section>
	);
}

function Shimmer({ className }) {
	return (
		<div
			className={`animate-pulse rounded-[var(--radius-card)] bg-black/[0.06] ${className}`}
		/>
	);
}

export default function Dashboard() {
	const { user, vault, ready } = useAuth();
	const { report, loading, error, run } = useHealth();
	const { openUnlock } = useUnlockModal();
	const navigate = useNavigate();

	if (!ready) return null;
	const live = Boolean(user) && vault.unlocked;
	const checks = report?.checks;
	const rows = rowsFor(live ? report : null);
	const rings = {
		weak: live ? (checks?.weak.metric ?? null) : null,
		breach: live ? (checks?.breached.metric ?? null) : null,
		reused: live ? (checks?.reused.metric ?? null) : null,
	};

	let overlay = null;
	if (!user) {
		overlay = (
			<StateOverlay
				title="Your passwords, locked down."
				actions={
					<>
						<Button variant="create" onClick={() => navigate("/signup")}>
							Sign up
						</Button>
						<Button variant="secondary" onClick={() => navigate("/login")}>
							Log in
						</Button>
					</>
				}
			>
				Sign up to start your vault.
			</StateOverlay>
		);
	} else if (!vault.set_up) {
		overlay = (
			<StateOverlay
				title="Finish setting up your master key"
				actions={
					<Button onClick={() => navigate("/signup?step=master")}>
						Set up
					</Button>
				}
			/>
		);
	} else if (!vault.unlocked) {
		overlay = (
			<StateOverlay
				title="Unlock to run your security checkup"
				actions={<Button onClick={openUnlock}>Unlock</Button>}
			/>
		);
	}

	const failed = checks?.integrity.failed ?? [];
	const showSkeleton = live && !report && !error;
	const tint = overlay ? "opacity-60 grayscale" : "";

	return (
		<div className="mx-auto max-w-5xl">
			<div className="mb-5 flex flex-wrap items-end justify-between gap-3">
				<div>
					<h1 className="text-2xl font-semibold">Dashboard</h1>
					<p className="text-ink-2">Your vault's security at a glance.</p>
				</div>
				{live && (
					<div className="flex items-center gap-3 text-sm text-ink-2">
						{report && <span>Checked {timeAgo(report.checked_at)}</span>}
						<Button variant="secondary" onClick={run} loading={loading}>
							<RefreshCw className="size-4" aria-hidden /> Re-run
						</Button>
					</div>
				)}
			</div>

			{live && error && (
				<div
					role="alert"
					className="mb-4 flex items-center justify-between gap-3 rounded-[var(--radius-control)] bg-danger-bg px-4 py-3 text-sm text-danger"
				>
					Couldn't run the checkup.
					<Button variant="secondary" onClick={run}>
						Retry
					</Button>
				</div>
			)}

			{live && report?.entry_count === 0 && (
				<div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-card)] border border-hairline bg-surface px-5 py-4">
					<p className="text-sm">
						Add your first credential or import from Chrome.
					</p>
					<div className="flex gap-2">
						<Button
							variant="create"
							onClick={() => navigate("/passwords?new=1")}
						>
							+ Add
						</Button>
						<Link to="/transfer">
							<Button variant="secondary">Import</Button>
						</Link>
					</div>
				</div>
			)}

			<div className="relative">
				{overlay}
				<div
					className={`grid gap-4 lg:grid-cols-12 ${tint}`}
					aria-hidden={overlay ? true : undefined}
				>
					<div className="lg:col-span-7">
						{showSkeleton ? (
							<Shimmer className="h-72" />
						) : (
							<Card title="Overall health" className="h-full">
								{failed.length > 0 && (
									<div
										role="alert"
										className="mb-3 flex items-center justify-between gap-3 rounded-[var(--radius-control)] bg-danger-bg px-3 py-2 text-sm text-danger"
									>
										<span className="flex items-center gap-2">
											<ShieldAlert className="size-4 shrink-0" aria-hidden />
											{plural(failed.length, "entry")} failed its integrity
											check: possible tampering.
										</span>
										<Link
											to={`/passwords?filter=tampered&open=${failed[0].id}`}
											className="font-medium underline"
										>
											View
										</Link>
									</div>
								)}
								<HealthGauge score={live ? (report?.score ?? null) : null} />
							</Card>
						)}
					</div>
					<div className="lg:col-span-5">
						{showSkeleton ? (
							<Shimmer className="h-72" />
						) : (
							<Card title="Key risks" className="h-full">
								<RadialRings values={rings} />
							</Card>
						)}
					</div>
					<div className="lg:col-span-12">
						{showSkeleton ? (
							<Shimmer className="h-96" />
						) : (
							<section className="divide-y divide-hairline overflow-hidden rounded-[var(--radius-card)] border border-hairline bg-surface shadow-[var(--shadow-card)]">
								<h2 className="px-5 pt-4 pb-1 font-medium">Security checks</h2>
								{rows.map(({ key, ...row }) => (
									<CheckRow key={key} {...row} />
								))}
							</section>
						)}
					</div>
				</div>
			</div>
		</div>
	);
}
