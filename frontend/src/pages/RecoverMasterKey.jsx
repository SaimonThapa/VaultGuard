import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import Alert from "../components/Alert.jsx";
import Button from "../components/Button.jsx";
import MasterKeyFields, {
	masterKeyReady,
} from "../components/MasterKeyFields.jsx";
import OtpStep from "../components/OtpStep.jsx";
import StepIndicator from "../components/StepIndicator.jsx";
import TextField from "../components/TextField.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { api } from "../lib/api.js";
import { clock, useCountdown } from "../lib/useCountdown.js";

const STEPS = ["Send code", "Verify", "Recovery key", "New key"];
const RECOVERY_FORMAT = /^[0-9A-HJKMNP-TV-Z]{26}$/; // Crockford base32, once dashes are stripped

const normalize = (text) =>
	text
		.toUpperCase()
		.replace(/[-\s]/g, "")
		.replace(/[IL]/g, "1")
		.replace(/O/g, "0");

// Forgot master key: emailed code + recovery key -> new master key. One final submit; if the
// server rejects something, jump back to the step that owns it (design.md §6.4).
export default function RecoverMasterKey() {
	const { user, ready, setVault } = useAuth();
	const { toast } = useToast();
	const navigate = useNavigate();
	const [step, setStep] = useState(0);
	const [code, setCode] = useState("");
	const [recoveryKey, setRecoveryKey] = useState("");
	const [newKey, setNewKey] = useState("");
	const [confirm, setConfirm] = useState("");
	const [errors, setErrors] = useState({});
	const [busy, setBusy] = useState(false);
	const [cooldown, startCooldown] = useCountdown(0);
	const [lockedFor, startLock] = useCountdown(0);

	if (!ready) return null;
	if (!user) return <Navigate to="/login?next=/recover-master-key" replace />;

	const sendCode = async () => {
		setBusy(true);
		setErrors({});
		try {
			await api("/api/vault/otp", {
				method: "POST",
				body: { purpose: "recover_master" },
				toast: false,
			});
			startCooldown(60);
			setStep(1);
		} catch (err) {
			if (err.status === 429) {
				startCooldown(err.retryAfter ?? 60);
				setStep(1); // a code was sent recently: carry on with it
			} else {
				setErrors({ send: err.message });
			}
		} finally {
			setBusy(false);
		}
	};

	const submit = async (e) => {
		e.preventDefault();
		if (!masterKeyReady(newKey, confirm)) return;
		setBusy(true);
		setErrors({});
		try {
			await api("/api/vault/recover", {
				method: "POST",
				toast: false,
				body: { code, recovery_key: recoveryKey, new_master_key: newKey },
			});
			setVault({ set_up: true, unlocked: true });
			toast("Master key reset. Your recovery key is unchanged.");
			navigate("/", { replace: true });
		} catch (err) {
			if (err.code === "invalid_otp") {
				setCode(""); // only a bad code is cleared; after a bad recovery key it is still valid
				setStep(1);
				setErrors({
					otp: "That code didn't work. Check it or request a new one.",
				});
			} else if (err.code === "invalid_master_key") {
				const left = err.body.attempts_left;
				setStep(2);
				setErrors({
					recovery:
						left <= 2
							? `That recovery key didn't work. ${left} attempt${left === 1 ? "" : "s"} left before a 15-minute lockout.`
							: "That recovery key didn't work.",
				});
			} else if (err.status === 429) {
				startLock(err.retryAfter ?? 60);
			} else if (err.status === 422) {
				setErrors({
					newKey:
						"Use a strong master key that differs from your account password.",
				});
			} else {
				setErrors({ send: err.message });
			}
		} finally {
			setBusy(false);
		}
	};

	const recoveryValid = RECOVERY_FORMAT.test(normalize(recoveryKey));
	const locked = lockedFor > 0;

	return (
		<div>
			<Link
				to="/"
				className="mb-4 inline-flex items-center gap-1 text-sm text-ink-2 hover:underline"
			>
				<ArrowLeft className="size-4" aria-hidden /> Back to vault
			</Link>
			<StepIndicator steps={STEPS} current={step} />
			<h1 className="mb-1 text-xl font-semibold">Reset your master key</h1>

			{step === 0 && (
				<div>
					<p className="mb-5 text-sm text-ink-2">
						To reset your master key you need <strong>both</strong> a code sent
						to your email <strong>and</strong> your recovery key.
					</p>
					<Alert>{errors.send}</Alert>
					<Button className="w-full" loading={busy} onClick={sendCode}>
						Send code
					</Button>
					<p className="mt-4 text-center text-sm">
						<Link to="/reset-vault" className="text-ink-2 underline">
							Lost your recovery key too?
						</Link>
					</p>
				</div>
			)}

			{step === 1 && (
				<OtpStep
					code={code}
					onCode={setCode}
					error={errors.otp}
					cooldown={cooldown}
					onResend={sendCode}
					onContinue={() => {
						setErrors({});
						setStep(2);
					}}
				/>
			)}

			{step === 2 && (
				<div>
					<p className="mb-5 text-sm text-ink-2">
						Enter the recovery key you saved when you set up your vault.
					</p>
					<TextField
						label="Recovery key"
						className="mb-5 [&_input]:font-mono"
						value={recoveryKey}
						onChange={(e) => setRecoveryKey(e.target.value)}
						placeholder="XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XX"
						hint="Dashes and case don't matter."
						error={errors.recovery}
						autoComplete="off"
						spellCheck={false}
					/>
					<Button
						className="w-full"
						disabled={!recoveryValid}
						onClick={() => {
							setErrors({});
							setStep(3);
						}}
					>
						Continue
					</Button>
				</div>
			)}

			{step === 3 && (
				<form onSubmit={submit} noValidate>
					<p className="mb-5 text-sm text-ink-2">Choose your new master key.</p>
					<Alert>
						{locked
							? `Too many attempts. Try again in ${clock(lockedFor)}.`
							: errors.send}
					</Alert>
					<div className="mb-5">
						<MasterKeyFields
							value={newKey}
							confirm={confirm}
							onValue={setNewKey}
							onConfirm={setConfirm}
							serverError={errors.newKey}
						/>
					</div>
					<Button
						type="submit"
						loading={busy}
						disabled={locked || !masterKeyReady(newKey, confirm)}
						className="w-full"
					>
						Reset master key
					</Button>
				</form>
			)}
		</div>
	);
}
