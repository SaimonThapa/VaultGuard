import { useId } from "react";

// Visible label (never placeholder-only), inline error, correct autocomplete.
export default function TextField({
	label,
	error,
	hint,
	className = "",
	children,
	...input
}) {
	const id = useId();
	return (
		<div className={className}>
			<label htmlFor={id} className="mb-1.5 block text-sm font-medium">
				{label}
			</label>
			<div className="relative">
				<input
					id={id}
					aria-invalid={error ? "true" : undefined}
					aria-describedby={error || hint ? `${id}-msg` : undefined}
					className={`h-10 w-full rounded-[var(--radius-control)] border bg-surface px-3 text-[15px] placeholder:text-ink-3 ${
						error ? "border-danger" : "border-hairline"
					} ${children ? "pr-11" : ""}`}
					{...input}
				/>
				{children}
			</div>
			{(error || hint) && (
				<p
					id={`${id}-msg`}
					className={`mt-1.5 text-sm ${error ? "text-danger" : "text-ink-2"}`}
				>
					{error || hint}
				</p>
			)}
		</div>
	);
}
