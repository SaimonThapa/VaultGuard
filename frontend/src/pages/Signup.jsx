import { useEffect, useRef, useState } from "react";
import {
	Link,
	Navigate,
	useLocation,
	useNavigate,
	useSearchParams,
} from "react-router";
import Alert from "../components/Alert.jsx";
import Button from "../components/Button.jsx";
import OtpInput from "../components/OtpInput.jsx";
import PasswordField, { StrengthHint } from "../components/PasswordField.jsx";
import StepIndicator from "../components/StepIndicator.jsx";
import TextField from "../components/TextField.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { api } from "../lib/api.js";
import { MIN_SCORE, strengthOf } from "../lib/strength.js";
import { clock, useCountdown } from "../lib/useCountdown.js";
import MasterKeySetup from "./MasterKeySetup.jsx";

const STEPS = ["Account", "Verify email", "Master key"];
const USERNAME_RULE = /^[a-zA-Z0-9_.-]{3,32}$/;
const EMAIL_RULE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Only the non-secret username goes in the URL, so a refresh keeps your place.
export default function Signup() {
	const { user, ready } = useAuth();
	const [params] = useSearchParams();
	const step = params.get("step") ?? "account";
	if (!ready) return null;
	// Signed-in users only belong on step 3 (verification signs you in, so verify hands over to it).
	if (user && step === "verify")
		return <Navigate to="/signup?step=master" replace />;
	if (user && step !== "master") return <Navigate to="/" replace />;
	if (!user && step === "master") return <Navigate to="/login" replace />;
	if (step === "verify") return <VerifyStep username={params.get("u") ?? ""} />;
	if (step === "master") return <MasterKeySetup />;
	return <AccountStep />;
}

function AccountStep() {
	const { toast } = useToast();
	const navigate = useNavigate();
	const [form, setForm] = useState({
		username: "",
		email: "",
		password: "",
		confirm: "",
	});
	const [error, setError] = useState("");
	const [busy, setBusy] = useState(false);
	const [touched, setTouched] = useState(false);
	const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

	const strength = form.password
		? strengthOf(form.password, [form.username, form.email])
		: null;
	const problems = {
		username:
			!USERNAME_RULE.test(form.username) &&
			"3–32 characters: letters, digits, _ . -",
		email: !EMAIL_RULE.test(form.email) && "Enter a valid email address.",
		password:
			(form.password.length < 12 || form.password.length > 128) &&
			"Use 12–128 characters.",
		strong:
			strength && strength.score < MIN_SCORE && "Choose a stronger password.",
		confirm: form.confirm !== form.password && "The passwords don't match.",
	};
	const invalid = Object.values(problems).some(Boolean) || !strength;

	const submit = async (e) => {
		e.preventDefault();
		setTouched(true);
		if (invalid) return;
		setError("");
		setBusy(true);
		try {
			const username = form.username.trim();
			await api("/api/auth/signup", {
				method: "POST",
				toast: false,
				body: { username, email: form.email.trim(), password: form.password },
			});
			navigate(`/signup?step=verify&u=${encodeURIComponent(username)}`);
		} catch (err) {
			setError(err.message);
			if (err.status === 0 || err.status >= 500) toast(err.message, "error");
		} finally {
			setBusy(false);
		}
	};

	const show = (key) => touched && problems[key];
	return (
		<form onSubmit={submit} noValidate>
			<StepIndicator steps={STEPS} current={0} />
			<h1 className="mb-4 text-xl font-semibold">Create your account</h1>
			<Alert>{error}</Alert>
			<TextField
				label="Username"
				className="mb-4"
				value={form.username}
				onChange={set("username")}
				error={show("username")}
				autoComplete="username"
				autoFocus
			/>
			<TextField
				label="Email"
				type="email"
				className="mb-4"
				value={form.email}
				onChange={set("email")}
				error={show("email")}
				autoComplete="email"
			/>
			<div className="mb-4">
				<PasswordField
					label="Password"
					value={form.password}
					onChange={set("password")}
					error={show("password") || show("strong")}
					autoComplete="new-password"
				/>
				<StrengthHint strength={strength} />
			</div>
			<PasswordField
				label="Confirm password"
				className="mb-5"
				value={form.confirm}
				onChange={set("confirm")}
				error={show("confirm")}
				autoComplete="new-password"
			/>
			<Button type="submit" variant="create" loading={busy} className="w-full">
				Create account
			</Button>
			<p className="mt-4 text-center text-sm text-ink-2">
				Already have an account?{" "}
				<Link to="/login" className="font-medium text-ink underline">
					Log in
				</Link>
			</p>
		</form>
	);
}

function VerifyStep({ username }) {
	const { applySession } = useAuth();
	const { toast } = useToast();
	const navigate = useNavigate();
	const location = useLocation();
	const [code, setCode] = useState("");
	const [error, setError] = useState("");
	const [busy, setBusy] = useState(false);
	const [cooldown, startCooldown] = useCountdown(60); // a code was just sent
	const resentOnce = useRef(false);

	const resend = async () => {
		await api("/api/auth/resend-verification", {
			method: "POST",
			toast: false,
			body: { username },
		}).catch(() => {});
		startCooldown(60);
	};

	// Arriving from a login attempt on an unverified account: send a fresh code automatically.
	useEffect(() => {
		if (location.state?.resend && !resentOnce.current) {
			resentOnce.current = true;
			resend();
		}
	});

	const verify = async (value) => {
		setBusy(true);
		setError("");
		try {
			const data = await api("/api/auth/verify-email", {
				method: "POST",
				toast: false,
				body: { username, code: value },
			});
			applySession(data);
			navigate("/signup?step=master", { replace: true });
		} catch (err) {
			setCode("");
			setError(
				err.status === 400
					? "That code didn't work. Check it or request a new one."
					: err.message,
			);
			if (err.status === 0 || err.status >= 500) toast(err.message, "error");
		} finally {
			setBusy(false);
		}
	};

	return (
		<div>
			<StepIndicator steps={STEPS} current={1} />
			<h1 className="mb-1 text-xl font-semibold">Check your email</h1>
			<p className="mb-5 text-sm text-ink-2">
				We sent a 6-digit code to the address you entered.
			</p>
			<OtpInput
				value={code}
				onChange={setCode}
				onComplete={verify}
				error={error}
				disabled={busy}
			/>
			{import.meta.env.DEV && (
				<p className="mt-4 text-center text-xs text-ink-3">
					Dev mode: the code is printed in the backend console.
				</p>
			)}
			<Button
				className="mt-5 w-full"
				loading={busy}
				disabled={code.length < 6}
				onClick={() => verify(code)}
			>
				Verify
			</Button>
			<p className="mt-4 text-center text-sm text-ink-2">
				Didn't get it?{" "}
				{cooldown > 0 ? (
					<span>Resend code ({clock(cooldown)})</span>
				) : (
					<button
						type="button"
						onClick={resend}
						className="font-medium text-ink underline"
					>
						Resend code
					</button>
				)}
			</p>
		</div>
	);
}
