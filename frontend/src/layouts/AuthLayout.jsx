import { Navigate, Outlet, useSearchParams } from "react-router";
import Logo from "../components/Logo.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { safeNext } from "../lib/format.js";

// No app shell: one centered glass card over a soft background (design.md §5.1).
// `guestOnly` pages (login, signup, forgot password) bounce signed-in users to the dashboard.
export default function AuthLayout({ guestOnly = false }) {
	const { user, ready } = useAuth();
	const [params] = useSearchParams();
	if (!ready) return null;
	if (guestOnly && user)
		return <Navigate to={safeNext(params.get("next"))} replace />;

	return (
		<main className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
			<div aria-hidden className="pointer-events-none absolute inset-0">
				<div className="absolute -top-32 -left-24 size-[28rem] rounded-full bg-black/[0.05] blur-3xl" />
				<div className="absolute -right-24 -bottom-32 size-[32rem] rounded-full bg-black/[0.06] blur-3xl" />
			</div>
			<div className="glass relative w-full max-w-[420px] rounded-[var(--radius-sheet)] p-8 shadow-[var(--shadow-float)]">
				<Logo className="mb-6" />
				<Outlet />
			</div>
		</main>
	);
}
