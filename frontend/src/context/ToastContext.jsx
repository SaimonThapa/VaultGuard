import { CircleAlert, CircleCheck } from "lucide-react";
import {
	createContext,
	useCallback,
	useContext,
	useMemo,
	useState,
} from "react";

const ToastContext = createContext(null);
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }) {
	const [toasts, setToasts] = useState([]);

	const toast = useCallback((message, kind = "success") => {
		const id = crypto.randomUUID();
		setToasts((t) => [...t, { id, message, kind }]);
		setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);
	}, []);

	const value = useMemo(() => ({ toast }), [toast]);
	return (
		<ToastContext.Provider value={value}>
			{children}
			<div
				aria-live="polite"
				className="pointer-events-none fixed top-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2"
			>
				{toasts.map((t) => (
					<div
						key={t.id}
						className="glass pointer-events-auto flex items-start gap-2.5 rounded-xl p-3 text-sm shadow-[var(--shadow-float)] [animation:toast-in_300ms_var(--ease-out)]"
					>
						{t.kind === "error" ? (
							<CircleAlert
								className="mt-0.5 size-4 shrink-0 text-danger"
								aria-hidden
							/>
						) : (
							<CircleCheck
								className="mt-0.5 size-4 shrink-0 text-create"
								aria-hidden
							/>
						)}
						<span>{t.message}</span>
					</div>
				))}
			</div>
		</ToastContext.Provider>
	);
}
