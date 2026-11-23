import { clock } from "../lib/useCountdown.js";
import Alert from "./Alert.jsx";
import Button from "./Button.jsx";
import OtpInput from "./OtpInput.jsx";

// "Enter the 6-digit code" step shared by the recovery flows. The code is only checked by the
// server at the final submit, so Continue just moves on.
export default function OtpStep({
	code,
	onCode,
	error,
	cooldown,
	onResend,
	onContinue,
}) {
	return (
		<div>
			<p className="mb-5 text-sm text-ink-2">
				We sent a 6-digit code to your account email.
			</p>
			<Alert>{error}</Alert>
			<OtpInput value={code} onChange={onCode} />
			{import.meta.env.DEV && (
				<p className="mt-4 text-center text-xs text-ink-3">
					Dev mode: the code is printed in the backend console.
				</p>
			)}
			<Button
				className="mt-5 w-full"
				disabled={code.length < 6}
				onClick={onContinue}
			>
				Continue
			</Button>
			<p className="mt-4 text-center text-sm text-ink-2">
				Didn't get it?{" "}
				{cooldown > 0 ? (
					<span>Resend code ({clock(cooldown)})</span>
				) : (
					<button
						type="button"
						onClick={onResend}
						className="font-medium text-ink underline"
					>
						Resend code
					</button>
				)}
			</p>
		</div>
	);
}
