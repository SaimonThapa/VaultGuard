import { initials } from "../lib/format.js";

// Monochrome initials: no favicon requests, so nothing leaks to third parties.
export default function LetterAvatar({ name, size = 32, square = false }) {
	return (
		<span
			aria-hidden
			style={{ width: size, height: size, fontSize: size * 0.38 }}
			className={`inline-flex shrink-0 items-center justify-center bg-black/[0.07] font-semibold text-ink-2 ${
				square ? "rounded-[10px]" : "rounded-full"
			}`}
		>
			{initials(name)}
		</span>
	);
}
