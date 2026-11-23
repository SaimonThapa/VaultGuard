import { useEffect, useRef } from "react";

// Six single-digit boxes. Paste fills all, Backspace goes back, the 6th digit calls onComplete.
export default function OtpInput({
	value,
	onChange,
	onComplete,
	error,
	disabled,
}) {
	const refs = useRef([]);
	const digits = Array.from({ length: 6 }, (_, i) => value[i] ?? "");

	useEffect(() => {
		if (value === "") refs.current[0]?.focus(); // cleared after an error
	}, [value]);

	const set = (next) => {
		onChange(next);
		if (next.length === 6) onComplete?.(next);
	};

	const onInput = (i, e) => {
		const typed = e.target.value.replace(/\D/g, "");
		if (!typed) return;
		const next = (value.slice(0, i) + typed).slice(0, 6);
		set(next);
		refs.current[Math.min(next.length, 5)]?.focus();
	};

	const onKeyDown = (i, e) => {
		if (e.key === "Backspace") {
			e.preventDefault();
			onChange(value.slice(0, digits[i] ? i : Math.max(0, i - 1)));
			refs.current[Math.max(0, digits[i] ? i : i - 1)]?.focus();
		}
	};

	const onPaste = (e) => {
		const pasted = e.clipboardData
			.getData("text")
			.replace(/\D/g, "")
			.slice(0, 6);
		if (!pasted) return;
		e.preventDefault();
		set(pasted);
	};

	return (
		<div>
			<fieldset className="flex justify-center gap-2">
				<legend className="sr-only">6-digit code</legend>
				{digits.map((d, i) => (
					<input
						// biome-ignore lint/suspicious/noArrayIndexKey: fixed six boxes, order never changes
						key={i}
						ref={(el) => {
							refs.current[i] = el;
						}}
						value={d}
						onChange={(e) => onInput(i, e)}
						onKeyDown={(e) => onKeyDown(i, e)}
						onPaste={onPaste}
						onFocus={(e) => e.target.select()}
						inputMode="numeric"
						autoComplete={i === 0 ? "one-time-code" : "off"}
						maxLength={6}
						disabled={disabled}
						aria-label={`Digit ${i + 1}`}
						aria-invalid={error ? "true" : undefined}
						className={`size-12 rounded-[var(--radius-control)] border bg-surface text-center font-mono text-xl ${
							error
								? "border-danger [animation:shake_300ms]"
								: "border-hairline"
						}`}
					/>
				))}
			</fieldset>
			{error && <p className="mt-2 text-center text-sm text-danger">{error}</p>}
		</div>
	);
}
