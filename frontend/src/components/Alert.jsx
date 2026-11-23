import { CircleAlert, Info } from "lucide-react";

// Inline message at the top of a card or form. kind: "error" | "warn" | "info".
const STYLES = {
	error: "bg-danger-bg text-danger",
	warn: "bg-warn-bg text-warn",
	info: "bg-black/[0.05] text-ink-2",
};

export default function Alert({ kind = "error", children }) {
	if (!children) return null;
	const Icon = kind === "info" ? Info : CircleAlert;
	return (
		<div
			role={kind === "error" ? "alert" : "status"}
			className={`mb-4 flex items-start gap-2 rounded-[var(--radius-control)] px-3 py-2.5 text-sm ${STYLES[kind]}`}
		>
			<Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
			<div>{children}</div>
		</div>
	);
}
