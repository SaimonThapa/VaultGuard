import { Copy, Eye, EyeOff } from "lucide-react";
import { useEffect, useState } from "react";
import { useToast } from "../../context/ToastContext.jsx";

const AUTO_HIDE_MS = 30_000;

// One labeled value with copy, and (for secrets) mask/reveal that re-masks after 30 s.
// Unmounting (row collapses, vault locks, page changes) re-masks too, since state is local.
export default function SecretField({
	label,
	value,
	secret = false,
	copyLabel,
}) {
	const { toast } = useToast();
	const [shown, setShown] = useState(false);

	useEffect(() => {
		if (!shown) return;
		const timer = setTimeout(() => setShown(false), AUTO_HIDE_MS);
		return () => clearTimeout(timer);
	}, [shown]);

	const copy = async () => {
		try {
			await navigator.clipboard.writeText(value);
			toast(`${copyLabel ?? label} copied`); // the value itself is never in the toast
		} catch {
			toast("Couldn't copy to the clipboard.", "error");
		}
	};

	const iconButton =
		"inline-flex size-8 items-center justify-center rounded-lg text-ink-2 hover:bg-black/5";
	return (
		<div className="flex items-center gap-3 py-1.5">
			<span className="w-24 shrink-0 text-sm text-ink-2">{label}</span>
			<span className="min-w-0 flex-1 font-mono text-sm break-all">
				{secret && !shown
					? "••••••••••"
					: value || <span className="text-ink-3">(empty)</span>}
			</span>
			{secret && (
				<button
					type="button"
					onClick={() => setShown((s) => !s)}
					aria-label={
						shown
							? `Hide ${label.toLowerCase()}`
							: `Show ${label.toLowerCase()}`
					}
					aria-pressed={shown}
					className={iconButton}
				>
					{shown ? (
						<EyeOff className="size-4" aria-hidden />
					) : (
						<Eye className="size-4" aria-hidden />
					)}
				</button>
			)}
			{value && (
				<button
					type="button"
					onClick={copy}
					aria-label={`Copy ${label.toLowerCase()}`}
					className={iconButton}
				>
					<Copy className="size-4" aria-hidden />
				</button>
			)}
		</div>
	);
}
