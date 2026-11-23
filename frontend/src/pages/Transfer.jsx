import { Download, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import Alert from "../components/Alert.jsx";
import Button from "../components/Button.jsx";
import FileDropZone, { precheck } from "../components/FileDropZone.jsx";
import PasswordField from "../components/PasswordField.jsx";
import StateOverlay from "../components/StateOverlay.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useHealth } from "../context/HealthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { useUnlockModal } from "../context/UnlockModalContext.jsx";
import { api } from "../lib/api.js";
import { clock, useCountdown } from "../lib/useCountdown.js";

const FIELD_NAMES = {
	site_name: "site name",
	site_url: "URL",
	username: "username",
	password: "password",
	notes: "notes",
	rotation_days: "rotation",
	integrity: "integrity check",
};

function Card({ title, children }) {
	return (
		<section className="rounded-[var(--radius-card)] border border-hairline bg-surface p-5 shadow-[var(--shadow-card)]">
			<h2 className="mb-4 font-medium">{title}</h2>
			{children}
		</section>
	);
}

function ImportCard() {
	const { toast } = useToast();
	const { run: refreshHealth } = useHealth();
	const [file, setFile] = useState(null);
	const [fileError, setFileError] = useState("");
	const [masterKey, setMasterKey] = useState("");
	const [keyError, setKeyError] = useState("");
	const [busy, setBusy] = useState(false);
	const [result, setResult] = useState(null);

	const isBackup = file?.name.toLowerCase().endsWith(".json");
	const choose = (picked) => {
		setFileError("");
		setKeyError("");
		if (picked) {
			const problem = precheck(picked);
			if (problem) {
				setFileError(problem); // nothing is uploaded
				return;
			}
		}
		setFile(picked);
	};

	const submit = async (e) => {
		e.preventDefault();
		if (!file || (isBackup && !masterKey)) return;
		setBusy(true);
		setFileError("");
		setKeyError("");
		const form = new FormData();
		form.append("file", file);
		if (isBackup) form.append("master_key", masterKey);
		try {
			const data = await api("/api/import", {
				method: "POST",
				form,
				toast: false,
			});
			setResult({ ...data, csv: !isBackup });
			setMasterKey("");
			toast("Import complete");
			refreshHealth();
		} catch (err) {
			if (err.code === "invalid_master_key")
				setKeyError("That master key doesn't open this backup.");
			else if (err.code === "invalid_import") {
				setFileError(
					"That file couldn't be imported. Use a Chrome/Google CSV or a VaultGuard backup under 1 MB.",
				);
			} else if (err.status !== 423) {
				setFileError(err.message);
			}
		} finally {
			setBusy(false);
		}
	};

	if (result) {
		return (
			<Card title="Import">
				<p className="mb-1 font-medium">
					Imported {result.imported} · Skipped {result.skipped_duplicates}{" "}
					duplicate
					{result.skipped_duplicates === 1 ? "" : "s"}
					{result.failed_rows.length > 0 &&
						` · ${result.failed_rows.length} rows failed`}
				</p>
				{result.failed_rows.length > 0 && (
					<p className="mb-3 text-sm text-ink-2">
						{result.failed_rows
							.slice(0, 8)
							.map((r) => `Row ${r.row}: ${FIELD_NAMES[r.reason] ?? r.reason}`)
							.join(" · ")}
						{result.failed_rows.length > 8 &&
							` · and ${result.failed_rows.length - 8} more`}
					</p>
				)}
				<div className="mt-4 flex flex-wrap gap-2">
					<Link to="/passwords">
						<Button>View passwords</Button>
					</Link>
					<Button
						variant="secondary"
						onClick={() => {
							setResult(null);
							setFile(null);
						}}
					>
						Import another
					</Button>
				</div>
				{result.csv && (
					<div className="mt-4 flex gap-2 rounded-[var(--radius-control)] bg-warn-bg p-3 text-sm text-warn">
						<TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
						Delete the CSV file from your computer. It contains your passwords
						in plain text.
					</div>
				)}
			</Card>
		);
	}

	return (
		<Card title="Import">
			<form onSubmit={submit} noValidate>
				<FileDropZone
					file={file}
					onFile={choose}
					error={fileError}
					disabled={busy}
				/>
				{isBackup && (
					<PasswordField
						label="Master key used for this backup"
						className="mt-4"
						value={masterKey}
						onChange={(e) => setMasterKey(e.target.value)}
						error={keyError}
						autoComplete="off"
						spellCheck={false}
						disabled={busy}
					/>
				)}
				<Button
					type="submit"
					variant="create"
					className="mt-4 w-full"
					loading={busy}
					disabled={!file || (isBackup && !masterKey)}
				>
					Import
				</Button>
			</form>
		</Card>
	);
}

function ExportCard() {
	const { toast } = useToast();
	const [masterKey, setMasterKey] = useState("");
	const [error, setError] = useState("");
	const [skipped, setSkipped] = useState(0);
	const [busy, setBusy] = useState(false);
	const [lockedFor, startLock] = useCountdown(0);

	const submit = async (e) => {
		e.preventDefault();
		if (!masterKey) return;
		setBusy(true);
		setError("");
		setSkipped(0);
		try {
			const res = await api("/api/export", {
				method: "POST",
				body: { master_key: masterKey },
				raw: true,
				toast: false,
			});
			const text = await res.text();
			const name =
				/filename="([^"]+)"/.exec(
					res.headers.get("Content-Disposition") ?? "",
				)?.[1] ?? "vaultguard-backup.json";
			const url = URL.createObjectURL(
				new Blob([text], { type: "application/json" }),
			);
			const link = document.createElement("a");
			link.href = url;
			link.download = name;
			link.click();
			URL.revokeObjectURL(url);
			setMasterKey("");
			setSkipped(JSON.parse(text).skipped_integrity ?? 0);
			toast("Backup downloaded");
		} catch (err) {
			setMasterKey("");
			if (err.status === 429) startLock(err.retryAfter ?? 60);
			else if (err.code === "invalid_master_key") {
				const left = err.body.attempts_left;
				setError(
					left <= 2
						? `Wrong master key. ${left} attempt${left === 1 ? "" : "s"} left before a 15-minute lockout.`
						: "Wrong master key.",
				);
			} else if (err.status !== 423) {
				setError(err.message);
			}
		} finally {
			setBusy(false);
		}
	};

	const locked = lockedFor > 0;
	return (
		<Card title="Export">
			<form onSubmit={submit} noValidate>
				<p className="mb-4 text-sm text-ink-2">
					Download an encrypted backup of all your credentials. Only your
					current master key can open it.
				</p>
				<Alert>
					{locked ? `Too many attempts. Try again in ${clock(lockedFor)}.` : ""}
				</Alert>
				{skipped > 0 && (
					<Alert kind="warn">
						{skipped} {skipped === 1 ? "entry" : "entries"} failed{" "}
						{skipped === 1 ? "its" : "their"} integrity check and{" "}
						{skipped === 1 ? "was" : "were"} left out.
					</Alert>
				)}
				<PasswordField
					label="Confirm master key"
					className="mb-4"
					value={masterKey}
					onChange={(e) => setMasterKey(e.target.value)}
					error={error}
					autoComplete="off"
					spellCheck={false}
					disabled={locked}
				/>
				<Button
					type="submit"
					loading={busy}
					disabled={locked || !masterKey}
					className="w-full"
				>
					<Download className="size-4" aria-hidden /> Export backup
				</Button>
				<p className="mt-3 text-center text-xs text-ink-3">
					VaultGuard never exports unencrypted passwords.
				</p>
			</form>
		</Card>
	);
}

export default function Transfer() {
	const { user, vault, ready } = useAuth();
	const { openUnlock } = useUnlockModal();
	if (!ready || !user) return null;
	const locked = !vault.unlocked;

	return (
		<div className="mx-auto max-w-5xl">
			<h1 className="text-2xl font-semibold">Import & Export</h1>
			<p className="mb-5 text-ink-2">
				Bring passwords in from Chrome, or back up your vault.
			</p>
			<div className="relative">
				{locked && (
					<StateOverlay
						title="Unlock to import or export"
						actions={<Button onClick={openUnlock}>Unlock</Button>}
					/>
				)}
				<div
					className={`grid items-start gap-4 lg:grid-cols-2 ${locked ? "pointer-events-none opacity-60 grayscale" : ""}`}
					aria-hidden={locked || undefined}
					inert={locked || undefined}
				>
					<ImportCard />
					<ExportCard />
				</div>
			</div>
		</div>
	);
}
