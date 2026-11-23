import { useState } from "react";
import { Link, useNavigate } from "react-router";
import Alert from "../components/Alert.jsx";
import Button from "../components/Button.jsx";
import OtpInput from "../components/OtpInput.jsx";
import PasswordField, { StrengthHint } from "../components/PasswordField.jsx";
import StepIndicator from "../components/StepIndicator.jsx";
import TextField from "../components/TextField.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { api } from "../lib/api.js";
import { MIN_SCORE, strengthOf } from "../lib/strength.js";
import { clock, useCountdown } from "../lib/useCountdown.js";

// Forgot *account* password: email, then code + new password. The vault is untouched.
export default function ForgotPassword() {
	const { toast } = useToast();
	const navigate = useNavigate();
	const [step, setStep] = useState(0);
	const [email, setEmail] = useState("");
	const [code, setCode] = useState("");
	const [password, setPassword] = useState("");
	const [confirm, setConfirm] = useState("");
	const [error, setError] = useState("");
	const [codeError, setCodeError] = useState("");
	const [busy, setBusy] = useState(false);
	const [cooldown, startCooldown] = useCountdown(0);

	const strength = password ? strengthOf(password, [email]) : null;
	const passwordProblem =
		touchedProblem(password, strength) ||
		(confirm !== password && "The passwords don't match.");

	const run = async (fn) => {
		setBusy(true);
		setError("");
		try {
			await fn();
		} catch (err) {
			setError(err.message);
			if (err.status === 0 || err.status >= 500) toast(err.message, "error");
		} finally {
			setBusy(false);
		}
	};

	const sendCode = (e) => {
		e?.preventDefault();
		return run(async () => {
			await api("/api/auth/forgot-password", {
				method: "POST",
				toast: false,
				body: { email: email.trim() },
			});
			startCooldown(60);
			setStep(1); // same neutral next step whether or not the account exists
		});
	};

	const reset = (e) => {
		e.preventDefault();
		setCodeError("");
		if (passwordProblem || code.length < 6) return;
		return run(async () => {
			try {
				await api("/api/auth/reset-password", {
					method: "POST",
					toast: false,
					body: { email: email.trim(), code, new_password: password },
				});
			} catch (err) {
				if (err.status === 400) {
					setCode("");
					setCodeError("That code didn't work. Check it or request a new one.");
					return;
				}
				throw err;
			}
			toast("Password updated. Log in with your new password.");
			navigate("/login");
		});
	};

	return (
		<div>
			<StepIndicator steps={["Email", "Reset"]} current={step} />
			<h1 className="mb-1 text-xl font-semibold">Reset your password</h1>
			{step === 0 ? (
				<form onSubmit={sendCode} noValidate>
					<p className="mb-5 text-sm text-ink-2">
						Enter your account email. Your vault isn't affected by this.
					</p>
					<Alert>{error}</Alert>
					<TextField
						label="Email"
						type="email"
						className="mb-5"
						value={email}
						onChange={(e) => setEmail(e.target.value)}
						autoComplete="email"
						autoFocus
					/>
					<Button
						type="submit"
						loading={busy}
						disabled={!email.includes("@")}
						className="w-full"
					>
						Send code
					</Button>
				</form>
			) : (
				<form onSubmit={reset} noValidate>
					<p className="mb-5 text-sm text-ink-2">
						If an account exists for that email, we sent a 6-digit code.
						Resetting signs out your other sessions.
					</p>
					<Alert>{error}</Alert>
					<div className="mb-5">
						<OtpInput
							value={code}
							onChange={setCode}
							error={codeError}
							disabled={busy}
						/>
					</div>
					<div className="mb-4">
						<PasswordField
							label="New password"
							value={password}
							onChange={(e) => setPassword(e.target.value)}
							autoComplete="new-password"
						/>
						<StrengthHint strength={strength} />
					</div>
					<PasswordField
						label="Confirm new password"
						className="mb-5"
						value={confirm}
						onChange={(e) => setConfirm(e.target.value)}
						error={
							confirm && confirm !== password
								? "The passwords don't match."
								: ""
						}
						autoComplete="new-password"
					/>
					<Button
						type="submit"
						loading={busy}
						disabled={Boolean(passwordProblem) || code.length < 6}
						className="w-full"
					>
						Reset password
					</Button>
					<p className="mt-4 text-center text-sm text-ink-2">
						Didn't get it?{" "}
						{cooldown > 0 ? (
							<span>Resend code ({clock(cooldown)})</span>
						) : (
							<button
								type="button"
								onClick={sendCode}
								className="font-medium text-ink underline"
							>
								Resend code
							</button>
						)}
					</p>
				</form>
			)}
			<p className="mt-5 text-center text-sm">
				<Link to="/login" className="text-ink-2 underline">
					Back to log in
				</Link>
			</p>
		</div>
	);
}

function touchedProblem(password, strength) {
	if (password.length < 12 || password.length > 128)
		return "Use 12–128 characters.";
	if (!strength || strength.score < MIN_SCORE)
		return "Choose a stronger password.";
	return false;
}
