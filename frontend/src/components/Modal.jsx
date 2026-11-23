import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import Button from "./Button.jsx";

const FOCUSABLE =
	'a[href],button:not([disabled]),input:not([disabled]),select,textarea,[tabindex]:not([tabindex="-1"])';

// Glass dialog over a dimmed, blurred backdrop. Traps focus, closes on Esc, restores focus.
export default function Modal({ title, onClose, children }) {
	const box = useRef(null);

	useEffect(() => {
		const opener = document.activeElement;
		box.current?.querySelector(FOCUSABLE)?.focus();
		const onKey = (e) => {
			if (e.key === "Escape") onClose();
			if (e.key !== "Tab") return;
			const items = [...box.current.querySelectorAll(FOCUSABLE)];
			if (!items.length) return;
			const first = items[0];
			const last = items[items.length - 1];
			if (e.shiftKey && document.activeElement === first) {
				e.preventDefault();
				last.focus();
			} else if (!e.shiftKey && document.activeElement === last) {
				e.preventDefault();
				first.focus();
			}
		};
		document.addEventListener("keydown", onKey);
		return () => {
			document.removeEventListener("keydown", onKey);
			opener?.focus?.();
		};
	}, [onClose]);

	return (
		<div className="fixed inset-0 z-40 flex items-center justify-center bg-black/25 p-4 backdrop-blur-sm [animation:fade-in_200ms]">
			<div
				ref={box}
				role="dialog"
				aria-modal="true"
				aria-label={title}
				style={{ background: "rgb(255 255 255 / 0.95)" }}
				className="glass w-full max-w-md rounded-[var(--radius-sheet)] p-6 shadow-[var(--shadow-float)]"
			>
				<div className="mb-4 flex items-start justify-between gap-4">
					<h2 className="text-lg font-semibold">{title}</h2>
					<button
						type="button"
						onClick={onClose}
						aria-label="Close"
						className="-mt-1 -mr-2 inline-flex size-9 items-center justify-center rounded-full text-ink-2 hover:bg-black/5"
					>
						<X className="size-5" aria-hidden />
					</button>
				</div>
				{children}
			</div>
		</div>
	);
}

export function ConfirmDialog({
	title,
	body,
	confirmLabel,
	variant = "danger",
	onConfirm,
	onClose,
}) {
	return (
		<Modal title={title} onClose={onClose}>
			<p className="mb-6 text-sm text-ink-2">{body}</p>
			<div className="flex justify-end gap-2">
				<Button variant="secondary" onClick={onClose}>
					Cancel
				</Button>
				<Button variant={variant} onClick={onConfirm}>
					{confirmLabel}
				</Button>
			</div>
		</Modal>
	);
}
