import { Loader2 } from "lucide-react";

// Color means the action: black = neutral primary, green = create, red = destructive,
// outline = secondary (design.md §1.1).
const VARIANTS = {
	primary: "bg-ink text-white hover:bg-black",
	create: "bg-create text-white hover:bg-create-hover",
	danger: "bg-danger text-white hover:bg-danger-hover",
	"danger-outline": "border border-danger text-danger hover:bg-danger-bg",
	secondary: "border border-hairline bg-surface text-ink hover:bg-canvas",
	ghost: "text-ink-2 hover:bg-black/5",
};

export default function Button({
	variant = "primary",
	loading = false,
	className = "",
	children,
	disabled,
	type = "button",
	...rest
}) {
	return (
		<button
			type={type}
			disabled={disabled || loading}
			className={`inline-flex min-h-9 items-center justify-center gap-2 rounded-[var(--radius-control)] px-4 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
			{...rest}
		>
			{loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
			{children}
		</button>
	);
}
