import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { useUnlockModal } from "../context/UnlockModalContext.jsx";
import { clock, useCountdown } from "../lib/useCountdown.js";
import Alert from "./Alert.jsx";
import Button from "./Button.jsx";
import Modal from "./Modal.jsx";
import PasswordField from "./PasswordField.jsx";

// Global unlock prompt (design.md §6.1). Rendered once in App; opened from anywhere.
export default function UnlockModal() {
	const { open, closeUnlock } = useUnlockModal();
	if (!open) return null;
	return <UnlockDialog onClose={closeUnlock} />;
}

function UnlockDialog({ onClose }) {
	const { user, unlock, vault } = useAuth();
	const { toast } = useToast();
	const navigate = useNavigate();
	const [key, setKey] = useState("");
	const [error, setError] = useState("");
	const [busy, setBusy] = useState(false);
	const [lockedFor, startLock] = useCountdown(0);

	const submit = async (e) => {
		e.preventDefault();
		setBusy(true);
		setError("");
		try {
			await unlock(key);
			setKey("");
			onClose();
			toast("Vault unlocked");
		} catch (err) {
			setKey("");
			if (err.status === 429) {
				startLock(err.retryAfter ?? 60);
			} else if (err.code === "invalid_master_key") {
				const left = err.body.attempts_left;
				setError(
					left <= 2
						? `Wrong master key. ${left} attempt${left === 1 ? "" : "s"} left before a 15-minute lockout.`
						: "Wrong master key.",
				);
			} else if (err.code === "integrity_failed") {
				setError(
					"Your vault key failed its integrity check. The stored data may have been tampered with.",
				);
			} else if (err.code === "vault_not_set_up") {
				onClose();
				navigate("/signup?step=master");
			} else {
				setError(err.message);
				if (err.status === 0 || err.status >= 500) toast(err.message, "error");
			}
		} finally {
			setBusy(false);
		}
	};

	const locked = lockedFor > 0;
	return (
		<Modal title="Unlock your vault" onClose={onClose}>
			<form onSubmit={submit} noValidate>
				{user && (
					<p className="-mt-2 mb-4 text-sm text-ink-2">
						Signed in as {user.username}
					</p>
				)}
				<Alert>
					{locked
						? `Too many attempts. Try again in ${clock(lockedFor)}.`
						: error}
				</Alert>
				<PasswordField
					label="Master key"
					value={key}
					onChange={(e) => setKey(e.target.value)}
					autoComplete="off"
					spellCheck={false}
					disabled={locked}
					className="mb-4 [&_input]:font-mono"
				/>
				<Button
					type="submit"
					loading={busy}
					disabled={locked || !key || vault.unlocked}
					className="w-full"
				>
					Unlock
				</Button>
				<p className="mt-4 text-center text-sm">
					<Link
						to="/recover-master-key"
						onClick={onClose}
						className="text-ink-2 underline"
					>
						Forgot master key?
					</Link>
				</p>
				<p className="mt-3 text-center text-xs text-ink-3">
					Auto-locks after 10 min of inactivity.
				</p>
			</form>
		</Modal>
	);
}
