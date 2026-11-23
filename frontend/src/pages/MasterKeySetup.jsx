import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import Alert from "../components/Alert.jsx";
import Button from "../components/Button.jsx";
import MasterKeyFields, {
	masterKeyReady,
} from "../components/MasterKeyFields.jsx";
import RecoveryKeyCard from "../components/RecoveryKeyCard.jsx";
import StepIndicator from "../components/StepIndicator.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { api } from "../lib/api.js";

const STEPS = ["Account", "Verify email", "Master key"];

// Signup step 3: choose the master key (3a), then see the recovery key once (3b).
export default function MasterKeySetup() {
	const { user, setVault } = useAuth();
	const { toast } = useToast();
	const navigate = useNavigate();
	const [key, setKey] = useState("");
	const [confirm, setConfirm] = useState("");
	const [error, setError] = useState("");
	const [busy, setBusy] = useState(false);
	const [recoveryKey, setRecoveryKey] = useState(null);
	const [saved, setSaved] = useState(false);

	// The recovery key is shown once: warn before the tab closes while it's on screen.
	useEffect(() => {
		if (!recoveryKey) return;
		const warn = (e) => e.preventDefault();
		window.addEventListener("beforeunload", warn);
		return () => window.removeEventListener("beforeunload", warn);
	}, [recoveryKey]);

	const ready = masterKeyReady(key, confirm);

	const submit = async (e) => {
		e.preventDefault();
		if (!ready) return;
		setBusy(true);
		setError("");
		try {
			const data = await api("/api/vault/setup", {
				method: "POST",
				toast: false,
				body: { master_key: key },
			});
			setKey("");
			setConfirm("");
			setVault({ set_up: true, unlocked: true });
			setRecoveryKey(data.recovery_key);
		} catch (err) {
			setError(
				err.status === 422
					? "Use a strong master key that differs from your account password."
					: err.message,
			);
			if (err.status === 0 || err.status >= 500) toast(err.message, "error");
		} finally {
			setBusy(false);
		}
	};

	if (recoveryKey) {
		return (
			<div>
				<StepIndicator steps={STEPS} current={3} />
				<h1 className="mb-1 text-xl font-semibold">Save your recovery key</h1>
				<p className="mb-5 text-sm text-ink-2">
					If you forget your master key, this key plus an email code is the only
					way back into your vault. It will not be shown again.
				</p>
				<RecoveryKeyCard
					recoveryKey={recoveryKey}
					username={user.username}
					checked={saved}
					onChecked={setSaved}
				/>
				<Button
					className="mt-5 w-full"
					disabled={!saved}
					onClick={() => {
						toast("Your vault is ready.");
						navigate("/", { replace: true });
					}}
				>
					Finish
				</Button>
			</div>
		);
	}

	return (
		<form onSubmit={submit} noValidate>
			<StepIndicator steps={STEPS} current={2} />
			<h1 className="mb-1 text-xl font-semibold">Set your master key</h1>
			<p className="mb-5 text-sm text-ink-2">
				This key encrypts your vault. We never store it, and we can't recover it
				for you.
			</p>
			<Alert>{error}</Alert>
			<div className="mb-5">
				<MasterKeyFields
					value={key}
					confirm={confirm}
					onValue={setKey}
					onConfirm={setConfirm}
				/>
			</div>
			<Button type="submit" loading={busy} disabled={!ready} className="w-full">
				Continue
			</Button>
		</form>
	);
}
