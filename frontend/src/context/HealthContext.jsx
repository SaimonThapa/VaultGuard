import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { api } from "../lib/api.js";
import { useAuth } from "./AuthContext.jsx";

// One health report shared by the Dashboard and the Passwords badges. It runs when the vault
// unlocks, and again whenever a page calls run() (re-run button, after add/edit/delete).
const HealthContext = createContext(null);
export const useHealth = () => useContext(HealthContext);

export function HealthProvider({ children }) {
	const { user, vault } = useAuth();
	const [report, setReport] = useState(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(false);
	const latest = useRef(0);

	const run = useCallback(async () => {
		const ticket = ++latest.current; // ignore a slow response that arrives after a newer one
		setLoading(true);
		setError(false);
		try {
			const data = await api("/api/vault/health");
			if (ticket === latest.current) setReport(data);
		} catch (err) {
			if (ticket === latest.current && err.status !== 423) setError(true);
		} finally {
			if (ticket === latest.current) setLoading(false);
		}
	}, []);

	const unlocked = Boolean(user) && vault.unlocked;
	useEffect(() => {
		if (unlocked) {
			run();
		} else {
			latest.current++;
			setReport(null); // locked: the report (names of weak entries) is not kept around
			setLoading(false);
			setError(false);
		}
	}, [unlocked, run]);

	const value = useMemo(
		() => ({ report, loading, error, run }),
		[report, loading, error, run],
	);
	return (
		<HealthContext.Provider value={value}>{children}</HealthContext.Provider>
	);
}
