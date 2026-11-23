import { ArrowLeft, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import Alert from "../components/Alert.jsx";
import Button from "../components/Button.jsx";
import MasterKeyFields, {
	masterKeyReady,
} from "../components/MasterKeyFields.jsx";
import OtpStep from "../components/OtpStep.jsx";
import RecoveryKeyCard from "../components/RecoveryKeyCard.jsx";
import StepIndicator from "../components/StepIndicator.jsx";
import TextField from "../components/TextField.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { api } from "../lib/api.js";
import { useCountdown } from "../lib/useCountdown.js";

const STEPS = ["Confirm", "Verify", "New key", "Recovery key"];

// Last resort when both the master key and recovery key are lost (design.md §6.5).
// Deletes every credential. The account stays.
export default function ResetVault() {
	const { user, ready, setVault } = useAuth();
	const { toast } = useToast();
	const navigate = useNavigate();
	const [step, setStep] = useState(0);
	const [count, setCount] = useState(null);
	const [typed, setTyped] = useState("");
	const [code, setCode] = useState("");
	const [newKey, setNewKey] = useState("");
	const [confirm, setConfirm] = useState("");
	const [recoveryKey, setRecoveryKey] = useState(null);
	const [saved, setSaved] = useState(false);
	const [error, setError] = useState("");
	const [otpError, setOtpError] = useState("");
	const [busy, setBusy] = useState(false);
	const [cooldown, startCooldown] = useCountdown(0);

	// How many credentials are about to be deleted (the list works while locked).
	useEffect(() => {
		if (!user) return;
		api("/api/entries", { toast: false })
			.then((data) => setCount(data.entries.length))
			.catch(() => setCount(null));
	}, [user]);

	// The new recovery key is shown once: warn before the tab closes while it's on screen.
	useEffect(() => {
		if (!recoveryKey) return;
		const warn = (e) => e.preventDefault();
		window.addEventListener("beforeunload", warn);
		return () => window.removeEventListener("beforeunload", warn);
	}, [recoveryKey]);

	if (!ready) return null;
	if (!user) return <Navigate to="/login?next=/reset-vault" replace />;

	const sendCode = async () => {
		setBusy(true);
		setError("");
		try {
			await api("/api/vault/otp", {
				method: "POST",
				body: { purpose: "reset_vault" },
				toast: false,
			});
			startCooldown(60);
			setStep(1);
		} catch (err) {
			if (err.status === 429) {
				startCooldown(err.retryAfter ?? 60);
				setStep(1); // a code was sent recently: carry on with it
			} else {
				setError(err.message);
			}
		} finally {
			setBusy(false);
		}
	};

	const submit = async (e) => {
		e.preventDefault();
		if (!masterKeyReady(newKey, confirm)) return;
		setBusy(true);
		setError("");
		try {
			const data = await api("/api/vault/reset", {
				method: "POST",
				toast: false,
				body: { code, new_master_key: newKey },
			});
			setNewKey("");
			setConfirm("");
			setVault({ set_up: true, unlocked: true });
			setRecoveryKey(data.recovery_key);
			setStep(3);
		} catch (err) {
			if (err.code === "invalid_otp") {
				setCode("");
				setOtpError("That code didn't work. Check it or request a new one.");
				setStep(1);
			} else if (err.status === 422) {
				setError(
					"Use a strong master key that differs from your account password.",
				);
			} else {
				setError(err.message);
			}
		} finally {
			setBusy(false);
		}
	};

	return (
		<div>
			<Link
				to="/"
				className="mb-4 inline-flex items-center gap-1 text-sm text-ink-2 hover:underline"
			>
				<ArrowLeft className="size-4" aria-hidden /> Back to vault
			</Link>
			<StepIndicator steps={STEPS} current={step} />
			<h1 className="mb-1 text-xl font-semibold">Reset your vault</h1>

			{step === 0 && (
				<div>
					<div className="mb-5 flex gap-2 rounded-[var(--radius-control)] bg-danger-bg p-3 text-sm text-danger">
						<TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
						<p>
							This permanently deletes{" "}
							<strong>
								{count == null
									? "all credentials"
									: `all ${count} credential${count === 1 ? "" : "s"}`}
							</strong>{" "}
							in your vault. Your account stays, and you'll set a new master
							key. This can't be undone.
						</p>
					</div>
					<Alert>{error}</Alert>
					<TextField
						label={`Type ${user.username} to confirm`}
						className="mb-5"
						value={typed}
						onChange={(e) => setTyped(e.target.value)}
						autoComplete="off"
					/>
					<div className="grid grid-cols-2 gap-3">
						<Button variant="secondary" onClick={() => navigate("/")}>
							Cancel
						</Button>
						<Button
							variant="danger"
							loading={busy}
							disabled={typed !== user.username}
							onClick={sendCode}
						>
							Continue
						</Button>
					</div>
				</div>
			)}

			{step === 1 && (
				<OtpStep
					code={code}
					onCode={setCode}
					error={otpError}
					cooldown={cooldown}
					onResend={sendCode}
					onContinue={() => {
						setOtpError("");
						setStep(2);
					}}
				/>
			)}

			{step === 2 && (
				<form onSubmit={submit} noValidate>
					<p className="mb-5 text-sm text-ink-2">
						Choose a new master key for your empty vault.
					</p>
					<Alert>{error}</Alert>
					<div className="mb-5">
						<MasterKeyFields
							value={newKey}
							confirm={confirm}
							onValue={setNewKey}
							onConfirm={setConfirm}
						/>
					</div>
					<Button
						type="submit"
						variant="danger"
						loading={busy}
						disabled={!masterKeyReady(newKey, confirm)}
						className="w-full"
					>
						Delete vault and start over
					</Button>
				</form>
			)}

			{step === 3 && recoveryKey && (
				<div>
					<p className="mb-5 text-sm text-ink-2">
						Save your new recovery key. It will not be shown again, and your old
						one no longer works.
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
							toast("Vault reset.");
							navigate("/", { replace: true });
						}}
					>
						Finish
					</Button>
				</div>
			)}
		</div>
	);
}
