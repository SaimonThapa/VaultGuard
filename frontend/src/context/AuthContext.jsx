import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { api, configureApi, setAccessToken } from "../lib/api.js";
import { useToast } from "./ToastContext.jsx";
import { useUnlockModal } from "./UnlockModalContext.jsx";

// All auth state lives here. The access token stays in memory only (never storage or URLs).
const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

const NO_VAULT = { set_up: false, unlocked: false };
const STATUS_POLL_MS = 60_000;

export function AuthProvider({ children }) {
	const { toast } = useToast();
	const { openUnlock } = useUnlockModal();
	const [user, setUser] = useState(null);
	const [vault, setVault] = useState(NO_VAULT);
	const [ready, setReady] = useState(false); // first session restore finished
	const refreshing = useRef(null);

	const applySession = useCallback((data) => {
		setAccessToken(data.access_token);
		setUser(data.user);
		setVault(data.vault);
	}, []);

	const clearSession = useCallback(() => {
		setAccessToken(null);
		setUser(null);
		setVault(NO_VAULT);
	}, []);

	// One refresh at a time, even if several requests hit 401 together.
	const refresh = useCallback(() => {
		refreshing.current ??= api("/api/auth/refresh", {
			method: "POST",
			toast: false,
		})
			.then((data) => {
				applySession(data);
				return true;
			})
			.catch(() => false)
			.finally(() => {
				refreshing.current = null;
			});
		return refreshing.current;
	}, [applySession]);

	useEffect(() => {
		configureApi({
			refresh,
			toast,
			onLocked: () => {
				setVault((v) => ({ ...v, unlocked: false }));
				openUnlock();
			},
			onSessionLost: () => {
				clearSession();
				toast("Please log in again.", "error");
			},
		});
	}, [refresh, toast, openUnlock, clearSession]);

	// Restore the session on load.
	useEffect(() => {
		refresh().finally(() => setReady(true));
	}, [refresh]);

	// While unlocked, notice the server's idle auto-lock.
	useEffect(() => {
		if (!vault.unlocked) return;
		const timer = setInterval(async () => {
			try {
				const status = await api("/api/vault/status", { toast: false });
				if (!status.unlocked) {
					setVault((v) => ({ ...v, unlocked: false }));
					toast("Vault locked after inactivity");
				}
			} catch {
				// a 401 is handled by the api client
			}
		}, STATUS_POLL_MS);
		return () => clearInterval(timer);
	}, [vault.unlocked, toast]);

	const login = useCallback(
		async (username, password) => {
			const data = await api("/api/auth/login", {
				method: "POST",
				body: { username, password },
				toast: false,
			});
			applySession(data);
			return data;
		},
		[applySession],
	);

	const logout = useCallback(async () => {
		await api("/api/auth/logout", { method: "POST", toast: false }).catch(
			() => {},
		);
		clearSession();
	}, [clearSession]);

	const unlock = useCallback(async (masterKey) => {
		await api("/api/vault/unlock", {
			method: "POST",
			body: { master_key: masterKey },
			toast: false,
		});
		setVault((v) => ({ ...v, unlocked: true }));
	}, []);

	const lock = useCallback(async () => {
		await api("/api/vault/lock", { method: "POST" });
		setVault((v) => ({ ...v, unlocked: false }));
	}, []);

	const value = useMemo(
		() => ({
			user,
			vault,
			ready,
			setVault,
			applySession,
			login,
			logout,
			unlock,
			lock,
		}),
		[user, vault, ready, applySession, login, logout, unlock, lock],
	);
	return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
