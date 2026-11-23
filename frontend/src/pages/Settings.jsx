import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import Alert from "../components/Alert.jsx";
import Button from "../components/Button.jsx";
import MasterKeyFields, {
	masterKeyReady,
} from "../components/MasterKeyFields.jsx";
import PasswordField, { StrengthHint } from "../components/PasswordField.jsx";
import RecoveryKeyCard from "../components/RecoveryKeyCard.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { useUnlockModal } from "../context/UnlockModalContext.jsx";
import { api } from "../lib/api.js";
import { MIN_SCORE, strengthOf } from "../lib/strength.js";
import { clock, useCountdown } from "../lib/useCountdown.js";

function Section({ title, danger = false, children }) {
	return (
		<section className="mb-6">
			<h2 className="mb-2 px-1 text-sm font-medium text-ink-2">{title}</h2>
			<div
				className={`divide-y divide-hairline overflow-hidden rounded-[var(--radius-card)] border bg-surface shadow-[var(--shadow-card)] ${
					danger ? "border-danger" : "border-hairline"
				}`}
			>
				{children}
			</div>
		</section>
	);
}

function Row({ label, value, action, children }) {
	return (
		<div className="px-4 py-3">
			<div className="flex min-h-9 items-center gap-3">
				<span className="w-28 shrink-0 text-sm text-ink-2">{label}</span>
				<span className="min-w-0 flex-1 truncate text-sm">{value}</span>
				{action}
			</div>
			{children}
		</div>
	);
}

function ChangePassword({ onDone }) {
	const { user } = useAuth();
	const { toast } = useToast();
	const [current, setCurrent] = useState("");
	const [next, setNext] = useState("");
	const [confirm, setConfirm] = useState("");
	const [errors, setErrors] = useState({});
	const [busy, setBusy] = useState(false);
	const [lockedFor, startLock] = useCountdown(0);

	const strength = next ? strengthOf(next, [user.username, user.email]) : null;
	const valid =
		current &&
		next.length >= 12 &&
		next.length <= 128 &&
		strength?.score >= MIN_SCORE &&
		confirm === next;

	const submit = async (e) => {
		e.preventDefault();
		if (!valid) return;
		setBusy(true);
		setErrors({});
		try {
			await api("/api/account/change-password", {
				method: "POST",
				toast: false,
				body: { current_password: current, new_password: next },
			});
			toast("Password updated. Other sessions were signed out.");
			onDone();
		} catch (err) {
			if (err.status === 400)
				setErrors({ current: "That isn't your current password." });
			else if (err.status === 429) startLock(err.retryAfter ?? 60);
			else if (err.status === 422)
				setErrors({ next: "Choose a stronger password." });
			else setErrors({ form: err.message });
			setCurrent("");
		} finally {
			setBusy(false);
		}
	};

	const locked = lockedFor > 0;
	return (
		<form onSubmit={submit} noValidate className="mt-4 grid gap-4">
			<Alert>
				{locked
					? `Too many attempts. Try again in ${clock(lockedFor)}.`
					: errors.form}
			</Alert>
			<PasswordField
				label="Current password"
				value={current}
				onChange={(e) => setCurrent(e.target.value)}
				error={errors.current}
				autoComplete="current-password"
			/>
			<div>
				<PasswordField
					label="New password"
					value={next}
					onChange={(e) => setNext(e.target.value)}
					error={errors.next}
					autoComplete="new-password"
				/>
				<StrengthHint strength={strength} />
			</div>
			<PasswordField
				label="Confirm new password"
				value={confirm}
				onChange={(e) => setConfirm(e.target.value)}
				error={confirm && confirm !== next ? "The passwords don't match." : ""}
				autoComplete="new-password"
			/>
			<div className="flex justify-end gap-2">
				<Button variant="secondary" onClick={onDone}>
					Cancel
				</Button>
				<Button type="submit" loading={busy} disabled={locked || !valid}>
					Update password
				</Button>
			</div>
		</form>
	);
}

function ChangeMasterKey({ onDone }) {
	const { toast } = useToast();
	const [count, setCount] = useState(null);
	const [key, setKey] = useState("");
	const [confirm, setConfirm] = useState("");
	const [error, setError] = useState("");
	const [busy, setBusy] = useState(false);
	const [recoveryKey, setRecoveryKey] = useState(null);
	const [saved, setSaved] = useState(false);
	const { user } = useAuth();

	useEffect(() => {
		api("/api/entries", { toast: false })
			.then((data) => setCount(data.entries.length))
			.catch(() => {});
	}, []);

	// The new recovery key is shown once: warn before the tab closes until Done.
	useEffect(() => {
		if (!recoveryKey) return;
		const warn = (e) => e.preventDefault();
		window.addEventListener("beforeunload", warn);
		return () => window.removeEventListener("beforeunload", warn);
	}, [recoveryKey]);

	const submit = async (e) => {
		e.preventDefault();
		if (!masterKeyReady(key, confirm)) return;
		setBusy(true);
		setError("");
		try {
			const data = await api("/api/vault/change-master-key", {
				method: "POST",
				toast: false,
				body: { new_master_key: key },
			});
			setKey("");
			setConfirm("");
			setRecoveryKey(data.recovery_key);
			toast("Master key changed. Vault re-encrypted.");
		} catch (err) {
			if (err.status === 409) {
				setError(
					"Some entries failed their integrity check, so nothing was changed. Check the dashboard.",
				);
			} else if (err.status === 422) {
				setError(
					"Use a strong master key that differs from your account password.",
				);
			} else if (err.status !== 423) {
				setError(err.message);
			}
		} finally {
			setBusy(false);
		}
	};

	if (recoveryKey) {
		return (
			<div className="mt-4">
				<p className="mb-4 text-sm text-ink-2">
					Save your new recovery key. It will not be shown again, and your old
					one no longer works.
				</p>
				<RecoveryKeyCard
					recoveryKey={recoveryKey}
					username={user.username}
					checked={saved}
					onChecked={setSaved}
				/>
				<div className="mt-4 flex justify-end">
					<Button disabled={!saved} onClick={onDone}>
						Done
					</Button>
				</div>
			</div>
		);
	}

	return (
		<form onSubmit={submit} noValidate className="mt-4">
			<p className="mb-4 text-sm text-ink-2">
				This re-encrypts all <strong>{count ?? "your"}</strong> credentials with
				a new key and gives you a <strong>new recovery key</strong>. Your
				current recovery key will stop working.
			</p>
			<Alert>{error}</Alert>
			<div className="mb-4">
				<MasterKeyFields
					value={key}
					confirm={confirm}
					onValue={setKey}
					onConfirm={setConfirm}
				/>
			</div>
			<div className="flex justify-end gap-2">
				<Button variant="secondary" onClick={onDone} disabled={busy}>
					Cancel
				</Button>
				<Button
					type="submit"
					loading={busy}
					disabled={!masterKeyReady(key, confirm)}
				>
					{busy ? "Re-encrypting…" : "Change master key"}
				</Button>
			</div>
		</form>
	);
}

export default function Settings() {
	const { user, vault } = useAuth();
	const { openUnlock } = useUnlockModal();
	const navigate = useNavigate();
	const [open, setOpen] = useState(null); // "password" | "master" | null: one at a time
	const [idle, setIdle] = useState(null);

	useEffect(() => {
		api("/api/vault/status", { toast: false })
			.then((s) => setIdle(s.idle_timeout_seconds))
			.catch(() => {});
	}, []);

	if (!user) return null;
	const toggle = (name) => setOpen((cur) => (cur === name ? null : name));
	const changeMaster = () => (vault.unlocked ? toggle("master") : openUnlock());

	return (
		<div className="mx-auto max-w-2xl">
			<h1 className="mb-6 text-2xl font-semibold">Settings</h1>

			<Section title="Account">
				<Row label="Username" value={user.username} />
				<Row label="Email" value={user.email} />
				<Row
					label="Password"
					value="••••••••••"
					action={
						<Button
							variant="secondary"
							onClick={() => toggle("password")}
							aria-expanded={open === "password"}
						>
							Change
						</Button>
					}
				>
					{open === "password" && (
						<ChangePassword onDone={() => setOpen(null)} />
					)}
				</Row>
			</Section>

			<Section title="Vault">
				<Row
					label="Master key"
					value="Re-encrypts your vault"
					action={
						<Button
							variant="secondary"
							onClick={changeMaster}
							aria-expanded={open === "master"}
						>
							Change
						</Button>
					}
				>
					{open === "master" && vault.unlocked && (
						<ChangeMasterKey onDone={() => setOpen(null)} />
					)}
				</Row>
				<Row
					label="Auto-lock"
					value={
						idle ? `After ${Math.round(idle / 60)} minutes of inactivity` : "…"
					}
				/>
			</Section>

			<Section title="Danger zone" danger>
				<Row
					label="Reset vault"
					value="Delete all credentials and start over"
					action={
						<Button
							variant="danger-outline"
							onClick={() => navigate("/reset-vault")}
						>
							Reset vault…
						</Button>
					}
				/>
			</Section>
		</div>
	);
}
