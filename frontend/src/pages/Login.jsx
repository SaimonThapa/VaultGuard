import { useRef, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import Alert from "../components/Alert.jsx";
import Button from "../components/Button.jsx";
import PasswordField from "../components/PasswordField.jsx";
import TextField from "../components/TextField.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useToast } from "../context/ToastContext.jsx";
import { useUnlockModal } from "../context/UnlockModalContext.jsx";
import { safeNext } from "../lib/format.js";
import { clock, useCountdown } from "../lib/useCountdown.js";

export default function Login() {
	const { login, user } = useAuth();
	const { toast } = useToast();
	const { openUnlock } = useUnlockModal();
	const navigate = useNavigate();
	const [params] = useSearchParams();
	const [username, setUsername] = useState("");
	const [password, setPassword] = useState("");
	const [error, setError] = useState("");
	const [busy, setBusy] = useState(false);
	const [lockedFor, startLock] = useCountdown(0);
	const passwordRef = useRef(null);
	const submitted = useRef(false); // a fresh login navigates itself; a revisit is redirected below

	const submit = async (e) => {
		e.preventDefault();
		setError("");
		setBusy(true);
		try {
			submitted.current = true;
			const data = await login(username.trim(), password);
			if (!data.vault.set_up) {
				navigate(
					`/signup?step=master&u=${encodeURIComponent(data.user.username)}`,
					{
						replace: true,
					},
				);
				return;
			}
			navigate(safeNext(params.get("next")), { replace: true });
			openUnlock(); // sign-in shows the locked vault, then asks for the master key
		} catch (err) {
			setPassword("");
			if (err.status === 429) {
				startLock(err.retryAfter ?? 60);
			} else if (err.status === 403) {
				navigate(
					`/signup?step=verify&u=${encodeURIComponent(username.trim())}`,
					{
						state: { resend: true },
					},
				);
			} else if (err.status === 401) {
				setError("Invalid username or password.");
				passwordRef.current?.focus();
			} else {
				setError(err.message);
				toast(err.message, "error");
			}
		} finally {
			setBusy(false);
		}
	};

	if (user && !submitted.current)
		return <Navigate to={safeNext(params.get("next"))} replace />;

	const locked = lockedFor > 0;
	return (
		<form onSubmit={submit} noValidate>
			<h1 className="mb-1 text-xl font-semibold">Sign in to your vault</h1>
			<p className="mb-5 text-sm text-ink-2">
				Use your account username and password.
			</p>
			<Alert>
				{locked
					? `Too many attempts. Try again in ${clock(lockedFor)}.`
					: error}
			</Alert>
			<TextField
				label="Username"
				className="mb-4"
				value={username}
				onChange={(e) => setUsername(e.target.value)}
				autoComplete="username"
				autoFocus
				required
			/>
			<PasswordField
				label="Password"
				className="mb-5"
				value={password}
				onChange={(e) => setPassword(e.target.value)}
				autoComplete="current-password"
				ref={passwordRef}
				required
			/>
			<Button
				type="submit"
				loading={busy}
				disabled={locked || !username || !password}
				className="w-full"
			>
				Log in
			</Button>
			<p className="mt-4 text-center text-sm">
				<Link to="/forgot-password" className="text-ink-2 underline">
					Forgot password?
				</Link>
			</p>
			<hr className="my-5 border-hairline" />
			<p className="text-center text-sm text-ink-2">
				New here?{" "}
				<Link to="/signup" className="font-medium text-ink underline">
					Create account
				</Link>
			</p>
		</form>
	);
}
