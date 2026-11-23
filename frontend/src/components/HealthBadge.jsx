import { ShieldAlert } from "lucide-react";

// Small data-colored pill on a password row. The label is always text, never color alone.
const KINDS = {
	weak: ["Weak", "bg-[#fdebd9] text-[#8a4200]"],
	reused: ["Reused", "bg-[#fdebd9] text-[#8a4200]"],
	breached: ["Breached", "bg-danger-bg text-danger"],
	rotation: ["Rotate due", "bg-warn-bg text-warn"],
	tampered: ["Tampered", "bg-danger-bg text-danger"],
};

export default function HealthBadge({ kind }) {
	const [label, style] = KINDS[kind];
	return (
		<span
			className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${style}`}
		>
			{kind === "tampered" && <ShieldAlert className="size-3.5" aria-hidden />}
			{label}
		</span>
	);
}
