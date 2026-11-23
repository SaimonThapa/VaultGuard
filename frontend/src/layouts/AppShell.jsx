import {
	ArrowLeftRight,
	ChevronsLeft,
	ChevronsRight,
	KeyRound,
	LayoutDashboard,
	ListChecks,
	LockKeyhole,
	LockKeyholeOpen,
	LogOut,
	Menu,
	Plus,
	Search,
	Settings,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
	Link,
	Navigate,
	NavLink,
	Outlet,
	useLocation,
	useNavigate,
} from "react-router";
import Button from "../components/Button.jsx";
import LetterAvatar from "../components/LetterAvatar.jsx";
import Logo from "../components/Logo.jsx";
import { ConfirmDialog } from "../components/Modal.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useUnlockModal } from "../context/UnlockModalContext.jsx";

const NAV = [
	{
		group: "Overview",
		items: [{ to: "/", label: "Dashboard", icon: LayoutDashboard, end: true }],
	},
	{
		group: "Vault",
		items: [
			{ to: "/passwords", label: "Passwords", icon: KeyRound },
			{ to: "/transfer", label: "Import / Export", icon: ArrowLeftRight },
		],
	},
	{
		group: "Security",
		items: [
			{ to: "/activity", label: "Activity log", icon: ListChecks },
			{ to: "/settings", label: "Settings", icon: Settings },
		],
	},
];

function Sidebar({ collapsed, onNavigate, onLogout }) {
	const { user } = useAuth();
	return (
		<nav aria-label="Main" className="flex h-full flex-col">
			<div className="flex-1 space-y-5 overflow-y-auto p-3">
				{NAV.map(({ group, items }) => (
					<div key={group}>
						{!collapsed && (
							<p className="mb-1 px-3 text-xs font-medium text-ink-3">
								{group}
							</p>
						)}
						<ul className="space-y-0.5">
							{items.map(({ to, label, icon: Icon, end }) => (
								<li key={to}>
									<NavLink
										to={to}
										end={end}
										onClick={onNavigate}
										title={collapsed ? label : undefined}
										className={({ isActive }) =>
											`flex min-h-9 items-center gap-3 rounded-[var(--radius-control)] px-3 text-sm ${
												isActive
													? "bg-black/[0.07] font-medium"
													: "text-ink-2 hover:bg-black/5"
											} ${collapsed ? "justify-center px-0" : ""}`
										}
									>
										<Icon className="size-[18px] shrink-0" aria-hidden />
										{!collapsed && label}
										{collapsed && <span className="sr-only">{label}</span>}
									</NavLink>
								</li>
							))}
						</ul>
					</div>
				))}
			</div>
			<div className="border-t border-hairline p-3">
				{user ? (
					<div
						className={`flex items-center gap-3 ${collapsed ? "justify-center" : ""}`}
					>
						<LetterAvatar name={user.username} />
						{!collapsed && (
							<>
								<span className="min-w-0 flex-1 truncate text-sm font-medium">
									{user.username}
								</span>
								<button
									type="button"
									onClick={onLogout}
									aria-label="Log out"
									className="inline-flex size-9 items-center justify-center rounded-full text-ink-2 hover:bg-black/5"
								>
									<LogOut className="size-[18px]" aria-hidden />
								</button>
							</>
						)}
					</div>
				) : (
					!collapsed && (
						<p className="px-1 text-sm text-ink-2">
							Not signed in ·{" "}
							<Link to="/login" className="font-medium text-ink underline">
								Log in
							</Link>
						</p>
					)
				)}
			</div>
		</nav>
	);
}

function AvatarMenu({ onLogout }) {
	const { user } = useAuth();
	const [open, setOpen] = useState(false);
	const ref = useRef(null);

	useEffect(() => {
		if (!open) return;
		const close = (e) => {
			if (
				e.type === "keydown"
					? e.key === "Escape"
					: !ref.current?.contains(e.target)
			)
				setOpen(false);
		};
		document.addEventListener("mousedown", close);
		document.addEventListener("keydown", close);
		return () => {
			document.removeEventListener("mousedown", close);
			document.removeEventListener("keydown", close);
		};
	}, [open]);

	return (
		<div ref={ref} className="relative">
			<button
				type="button"
				onClick={() => setOpen((o) => !o)}
				aria-label="Account menu"
				aria-expanded={open}
				className="inline-flex size-11 shrink-0 items-center justify-center rounded-full hover:bg-black/5 sm:size-9"
			>
				<LetterAvatar name={user.username} />
			</button>
			{open && (
				<div className="glass absolute right-0 mt-2 w-56 rounded-xl p-1.5 shadow-[var(--shadow-float)]">
					<div className="px-3 py-2">
						<p className="text-sm font-medium">{user.username}</p>
						<p className="truncate text-xs text-ink-3">{user.email}</p>
					</div>
					<Link
						to="/settings"
						onClick={() => setOpen(false)}
						className="flex min-h-9 items-center gap-2 rounded-lg px-3 text-sm hover:bg-black/5"
					>
						<Settings className="size-4" aria-hidden /> Settings
					</Link>
					<button
						type="button"
						onClick={() => {
							setOpen(false);
							onLogout();
						}}
						className="flex min-h-9 w-full items-center gap-2 rounded-lg px-3 text-sm hover:bg-black/5"
					>
						<LogOut className="size-4" aria-hidden /> Log out
					</button>
				</div>
			)}
		</div>
	);
}

// Header + sidebar around every page (design.md §2). Visitors may see the dashboard only.
export default function AppShell() {
	const { user, vault, ready, logout, lock } = useAuth();
	const { openUnlock } = useUnlockModal();
	const location = useLocation();
	const navigate = useNavigate();
	const searchRef = useRef(null);
	const [drawer, setDrawer] = useState(false);
	const [collapsed, setCollapsed] = useState(false);
	const [confirmLogout, setConfirmLogout] = useState(false);

	useEffect(() => {
		const onKey = (e) => {
			if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
				e.preventDefault();
				searchRef.current?.focus();
			}
		};
		document.addEventListener("keydown", onKey);
		return () => document.removeEventListener("keydown", onKey);
	}, []);

	if (!ready) return null;
	if (!user && location.pathname !== "/") {
		return (
			<Navigate
				to={`/login?next=${encodeURIComponent(location.pathname)}`}
				replace
			/>
		);
	}

	const needLogin = (path) =>
		navigate(user ? path : `/login?next=${encodeURIComponent(path)}`);
	const addCredential = () => {
		if (user && !vault.unlocked) return openUnlock();
		needLogin("/passwords?new=1");
	};
	const submitSearch = (e) => {
		e.preventDefault();
		const q = new FormData(e.currentTarget).get("q").toString().trim();
		needLogin(q ? `/passwords?q=${encodeURIComponent(q)}` : "/passwords");
	};
	const doLogout = async () => {
		setConfirmLogout(false);
		await logout();
		navigate("/login");
	};

	return (
		<div className="min-h-screen">
			<header className="glass fixed inset-x-0 top-0 z-30 flex h-14 items-center gap-3 border-x-0 border-t-0 px-3 sm:px-4">
				<button
					type="button"
					onClick={() => setDrawer(true)}
					aria-label="Open menu"
					className="inline-flex size-11 shrink-0 items-center justify-center rounded-full hover:bg-black/5 sm:size-9 lg:hidden"
				>
					<Menu className="size-5" aria-hidden />
				</button>
				<span className="hidden sm:block">
					<Logo />
				</span>
				<search className="mx-auto w-full max-w-md">
					<form onSubmit={submitSearch}>
						<label className="relative block">
							<span className="sr-only">Search credentials</span>
							<Search
								className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3"
								aria-hidden
							/>
							<input
								ref={searchRef}
								name="q"
								type="search"
								autoComplete="off"
								placeholder="Search credentials…"
								className="h-9 w-full rounded-[var(--radius-control)] bg-black/[0.06] pr-12 pl-9 text-sm placeholder:text-ink-3"
							/>
							<kbd className="pointer-events-none absolute top-1/2 right-3 hidden -translate-y-1/2 text-xs text-ink-3 sm:block">
								Ctrl K
							</kbd>
						</label>
					</form>
				</search>
				<Button
					variant="create"
					onClick={addCredential}
					className="min-h-11 shrink-0 px-3 sm:min-h-9 sm:px-4"
				>
					<Plus className="size-4" aria-hidden />
					<span className="hidden sm:inline">Add credential</span>
					<span className="sr-only sm:hidden">Add credential</span>
				</Button>
				{user ? (
					<>
						<button
							type="button"
							onClick={() => (vault.unlocked ? lock() : openUnlock())}
							aria-label={vault.unlocked ? "Lock vault" : "Unlock vault"}
							className={`inline-flex size-11 shrink-0 items-center justify-center rounded-full hover:bg-black/5 sm:size-9 ${
								vault.unlocked ? "text-ink-2" : "text-warn"
							}`}
						>
							{vault.unlocked ? (
								<LockKeyholeOpen className="size-5" aria-hidden />
							) : (
								<LockKeyhole className="size-5" aria-hidden />
							)}
						</button>
						<AvatarMenu onLogout={() => setConfirmLogout(true)} />
					</>
				) : (
					<div className="hidden items-center gap-2 sm:flex">
						<Link to="/login">
							<Button variant="secondary">Log in</Button>
						</Link>
						<Link to="/signup">
							<Button variant="create">Sign up</Button>
						</Link>
					</div>
				)}
			</header>

			<aside
				className={`glass fixed top-14 bottom-0 left-0 z-20 hidden border-y-0 border-l-0 transition-[width] lg:block ${
					collapsed ? "w-16" : "w-60"
				}`}
			>
				<Sidebar
					collapsed={collapsed}
					onLogout={() => setConfirmLogout(true)}
				/>
				<button
					type="button"
					onClick={() => setCollapsed((c) => !c)}
					aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
					className="absolute top-3 -right-3 inline-flex size-6 items-center justify-center rounded-full border border-hairline bg-surface text-ink-2 shadow-sm"
				>
					{collapsed ? (
						<ChevronsRight className="size-3.5" aria-hidden />
					) : (
						<ChevronsLeft className="size-3.5" aria-hidden />
					)}
				</button>
			</aside>

			{drawer && (
				<div className="fixed inset-0 z-40 lg:hidden">
					<button
						type="button"
						aria-label="Close menu"
						onClick={() => setDrawer(false)}
						className="absolute inset-0 bg-black/25 backdrop-blur-sm"
					/>
					<aside className="glass absolute inset-y-0 left-0 w-64">
						<Sidebar
							onNavigate={() => setDrawer(false)}
							onLogout={() => {
								setDrawer(false);
								setConfirmLogout(true);
							}}
						/>
					</aside>
				</div>
			)}

			<main
				className={`px-4 pt-20 pb-10 sm:px-6 ${collapsed ? "lg:pl-24" : "lg:pl-72"}`}
			>
				<Outlet />
			</main>

			{confirmLogout && (
				<ConfirmDialog
					title="Log out?"
					body="You'll need your account password and master key to get back in."
					confirmLabel="Log out"
					onConfirm={doLogout}
					onClose={() => setConfirmLogout(false)}
				/>
			)}
		</div>
	);
}
