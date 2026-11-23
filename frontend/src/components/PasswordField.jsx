import { Eye, EyeOff } from "lucide-react";
import { useEffect, useState } from "react";
import TextField from "./TextField.jsx";

// Password input with a show/hide toggle. Pass autoComplete ("new-password", "current-password"
// or "off" for master keys) explicitly.
export default function PasswordField({ revealToken, ...props }) {
	const [shown, setShown] = useState(false);
	// Bumping revealToken (e.g. after "Generate") shows the value so it can be read and copied.
	useEffect(() => {
		if (revealToken) setShown(true);
	}, [revealToken]);
	return (
		<TextField {...props} type={shown ? "text" : "password"}>
			<button
				type="button"
				onClick={() => setShown((s) => !s)}
				aria-label={shown ? "Hide password" : "Show password"}
				aria-pressed={shown}
				className="absolute top-0.5 right-0.5 inline-flex size-9 items-center justify-center rounded-lg text-ink-3 hover:bg-black/5"
			>
				{shown ? (
					<EyeOff className="size-[18px]" aria-hidden />
				) : (
					<Eye className="size-[18px]" aria-hidden />
				)}
			</button>
		</TextField>
	);
}

const SCORE_COLOR = [
	"var(--color-band-critical)",
	"var(--color-band-critical)",
	"var(--color-band-poor)",
	"var(--color-band-good)",
	"var(--color-band-excellent)",
];

// Live strength under a new-password field: a bar plus the label in text (never color alone).
export function StrengthHint({ strength }) {
	if (!strength) return null;
	return (
		<div className="mt-2" aria-live="polite">
			<div className="h-1.5 overflow-hidden rounded-full bg-black/[0.08]">
				<div
					className="h-full rounded-full transition-[width] duration-300"
					style={{
						width: `${((strength.score + 1) / 5) * 100}%`,
						background: SCORE_COLOR[strength.score],
					}}
				/>
			</div>
			<p className="mt-1 text-sm text-ink-2">
				<span className="font-medium text-ink">{strength.label}</span>
				{strength.score < 3 && strength.hint ? `. ${strength.hint}` : ""}
			</p>
		</div>
	);
}
