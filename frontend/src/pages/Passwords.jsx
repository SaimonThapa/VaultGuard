import { Plus, Search, Upload, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import Button from "../components/Button.jsx";
import { ConfirmDialog } from "../components/Modal.jsx";
import EntryForm from "../components/passwords/EntryForm.jsx";
import PasswordRow from "../components/passwords/PasswordRow.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useHealth } from "../context/HealthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { useUnlockModal } from "../context/UnlockModalContext.jsx";
import { api } from "../lib/api.js";

const FILTERS = {
	tampered: "Tampered",
	weak: "Weak",
	reused: "Reused",
	breached: "Breached",
	rotation: "Rotation due",
};

const SKELETON_ROWS = ["a", "b", "c", "d", "e", "f"];

function Skeleton() {
	return (
		<ul className="space-y-3" aria-busy="true" aria-label="Loading passwords">
			{SKELETON_ROWS.map((id) => (
				<li
					key={id}
					className="h-16 animate-pulse rounded-[var(--radius-card)] bg-black/[0.06]"
				/>
			))}
		</ul>
	);
}

// Each filter key maps to a badge kind (design.md §4.1).
const FILTER_KIND = {
	tampered: "tampered",
	weak: "weak",
	reused: "reused",
	breached: "breached",
	rotation: "rotation",
};

// entry id -> badge kinds, from the shared health report plus each entry's own integrity flag.
function badgesFrom(report, entries) {
	const map = new Map();
	const add = (id, kind) => map.set(id, [...(map.get(id) ?? []), kind]);
	for (const e of entries) if (e.integrity === "failed") add(e.id, "tampered");
	const c = report?.checks;
	if (!c) return map;
	for (const e of c.weak.entries) add(e.id, "weak");
	for (const group of c.reused.groups)
		for (const e of group) add(e.id, "reused");
	for (const e of c.breached.entries) add(e.id, "breached");
	for (const e of c.rotation.due) add(e.id, "rotation");
	return map;
}

export default function Passwords() {
	const { vault } = useAuth();
	const { toast } = useToast();
	const { openUnlock } = useUnlockModal();
	const { report, run: refreshHealth } = useHealth();
	const navigate = useNavigate();
	const [params, setParams] = useSearchParams();
	const urlQuery = params.get("q") ?? "";
	const filter = FILTERS[params.get("filter")] ? params.get("filter") : null;

	const [query, setQuery] = useState(urlQuery);
	const [data, setData] = useState(null); // { locked, entries }
	const [loading, setLoading] = useState(true);
	const [failed, setFailed] = useState(false);
	const [openId, setOpenId] = useState(null);
	const [form, setForm] = useState(null); // "new" | entry id | null
	const [dirty, setDirty] = useState(false);
	const [pending, setPending] = useState(null); // action waiting on "Discard changes?"
	const [deleting, setDeleting] = useState(null);
	const firstRender = useRef(true);

	const load = useCallback(async () => {
		setFailed(false);
		try {
			setData(await api(`/api/entries?q=${encodeURIComponent(query.trim())}`));
		} catch (err) {
			if (err.status !== 401) setFailed(true);
		} finally {
			setLoading(false);
		}
	}, [query]);

	// Debounced live search; also re-runs when the vault locks or unlocks.
	// biome-ignore lint/correctness/useExhaustiveDependencies: vault.unlocked is the refetch trigger
	useEffect(() => {
		const delay = firstRender.current ? 0 : 250;
		firstRender.current = false;
		const timer = setTimeout(load, delay);
		return () => clearTimeout(timer);
	}, [load, vault.unlocked]);

	// Locking discards forms and re-masks everything.
	useEffect(() => {
		if (!vault.unlocked) {
			setForm(null);
			setDirty(false);
		}
	}, [vault.unlocked]);

	// Header "Add credential" lands here with ?new=1.
	// biome-ignore lint/correctness/useExhaustiveDependencies: run once per ?new=1
	useEffect(() => {
		if (params.get("new") !== "1") return;
		const next = new URLSearchParams(params);
		next.delete("new");
		setParams(next, { replace: true });
		if (!vault.unlocked) openUnlock();
		else startForm("new");
	}, [params]);

	// The dashboard's tamper banner links here with ?open=<entry id>.
	const wantedOpen = params.get("open");
	useEffect(() => {
		if (wantedOpen && data?.entries.some((e) => e.id === wantedOpen))
			setOpenId(wantedOpen);
	}, [wantedOpen, data]);

	// The header search keeps ?q= in sync.
	useEffect(() => setQuery(urlQuery), [urlQuery]);

	const guard = (action) => (dirty ? setPending(() => action) : action());
	const closeForm = () => {
		setForm(null);
		setDirty(false);
	};
	function startForm(which) {
		guard(() => {
			setForm(which);
			setDirty(false);
			if (which !== "new") setOpenId(which);
		});
	}
	const toggle = (id) =>
		guard(() => {
			closeForm();
			setOpenId((cur) => (cur === id ? null : id));
		});

	const confirmDelete = async () => {
		const entry = deleting;
		setDeleting(null);
		try {
			await api(`/api/entries/${entry.id}`, { method: "DELETE", toast: false });
			toast("Deleted");
			setOpenId(null);
			load();
			refreshHealth();
		} catch (err) {
			if (err.status !== 423) toast(err.message, "error");
		}
	};

	const badgeMap = badgesFrom(report, data?.entries ?? []);
	const entries = (data?.entries ?? []).filter((e) => {
		if (!filter) return true;
		if (filter !== "tampered" && !report) return true; // no report yet: can't filter
		return (badgeMap.get(e.id) ?? []).includes(FILTER_KIND[filter]);
	});
	const locked = data?.locked ?? !vault.unlocked;
	const setQ = (value) => {
		setQuery(value);
		const next = new URLSearchParams(params);
		if (value) next.set("q", value);
		else next.delete("q");
		setParams(next, { replace: true });
	};

	return (
		<div className="mx-auto max-w-3xl">
			<h1 className="text-2xl font-semibold">All passwords</h1>
			<p className="mb-5 text-ink-2">
				Safely manage and access your passwords.
			</p>

			<div className="mb-3 flex flex-wrap gap-2">
				<label className="relative min-w-0 flex-1 basis-60">
					<span className="sr-only">Search by site or URL</span>
					<Search
						className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3"
						aria-hidden
					/>
					<input
						type="search"
						value={query}
						onChange={(e) => setQ(e.target.value)}
						placeholder="Search by site or URL…"
						autoComplete="off"
						maxLength={100}
						className="h-10 w-full rounded-[var(--radius-control)] border border-hairline bg-surface pr-3 pl-9"
					/>
				</label>
				<Link to="/transfer">
					<Button variant="secondary">
						<Upload className="size-4" aria-hidden /> Import
					</Button>
				</Link>
				<Button
					variant="create"
					onClick={() => (vault.unlocked ? startForm("new") : openUnlock())}
				>
					<Plus className="size-4" aria-hidden /> Add new
				</Button>
			</div>

			<div className="mb-4 flex items-center justify-between gap-2 text-sm text-ink-2">
				<span>
					{filter && (
						<button
							type="button"
							onClick={() => {
								const next = new URLSearchParams(params);
								next.delete("filter");
								setParams(next, { replace: true });
							}}
							className="inline-flex items-center gap-1 rounded-full bg-black/[0.07] px-2.5 py-1 text-ink"
						>
							Filter: {FILTERS[filter]}{" "}
							<X className="size-3.5" aria-label="Clear filter" />
						</button>
					)}
				</span>
				{data && (
					<span>
						{entries.length} credential{entries.length === 1 ? "" : "s"}
					</span>
				)}
			</div>

			{loading ? (
				<Skeleton />
			) : failed ? (
				<div className="rounded-[var(--radius-card)] border border-hairline bg-surface p-6 text-center">
					<p className="mb-3">Couldn't load your passwords.</p>
					<Button variant="secondary" onClick={load}>
						Retry
					</Button>
				</div>
			) : (
				<ul className="space-y-3">
					{form === "new" && (
						<li className="overflow-hidden rounded-[var(--radius-card)] border border-hairline bg-surface shadow-[var(--shadow-card)]">
							<EntryForm
								onDone={() => {
									closeForm();
									load();
									refreshHealth();
								}}
								onCancel={() => guard(closeForm)}
								onDirtyChange={setDirty}
							/>
						</li>
					)}
					{entries.map((entry) => (
						<PasswordRow
							key={entry.id}
							entry={entry}
							badges={badgeMap.get(entry.id)}
							locked={locked}
							open={openId === entry.id}
							editing={form === entry.id}
							onToggle={() => toggle(entry.id)}
							onEdit={() => startForm(entry.id)}
							onDelete={() => setDeleting(entry)}
							onUnlock={openUnlock}
							onFormDone={() => {
								closeForm();
								load();
								refreshHealth();
							}}
							onFormCancel={() => guard(closeForm)}
							onDirtyChange={setDirty}
						/>
					))}
				</ul>
			)}

			{!loading && !failed && entries.length === 0 && form !== "new" && (
				<div className="rounded-[var(--radius-card)] border border-hairline bg-surface p-8 text-center">
					{filter ? (
						<>
							<p className="mb-3">
								Nothing flagged as {FILTERS[filter]}. Nice.
							</p>
							<Button
								variant="secondary"
								onClick={() => setParams({}, { replace: true })}
							>
								Clear filter
							</Button>
						</>
					) : query.trim() ? (
						<>
							<p className="mb-3">No credentials match “{query.trim()}”.</p>
							<Button variant="secondary" onClick={() => setQ("")}>
								Clear search
							</Button>
						</>
					) : (
						<>
							<p className="mb-4 font-medium">No passwords yet.</p>
							<div className="flex flex-wrap justify-center gap-2">
								<Button
									variant="create"
									onClick={() =>
										vault.unlocked ? startForm("new") : openUnlock()
									}
								>
									<Plus className="size-4" aria-hidden /> Add new
								</Button>
								<Button
									variant="secondary"
									onClick={() => navigate("/transfer")}
								>
									<Upload className="size-4" aria-hidden /> Import from Chrome
								</Button>
							</div>
						</>
					)}
				</div>
			)}

			{deleting && (
				<ConfirmDialog
					title="Delete this password?"
					body={`Delete ${deleting.site_name}${deleting.username ? ` · ${deleting.username}` : ""}? This can't be undone.`}
					confirmLabel="Delete"
					onConfirm={confirmDelete}
					onClose={() => setDeleting(null)}
				/>
			)}
			{pending && (
				<ConfirmDialog
					title="Discard changes?"
					body="You have unsaved changes to this password."
					confirmLabel="Discard"
					onConfirm={() => {
						const action = pending;
						setPending(null);
						setDirty(false);
						action();
					}}
					onClose={() => setPending(null)}
				/>
			)}
		</div>
	);
}
