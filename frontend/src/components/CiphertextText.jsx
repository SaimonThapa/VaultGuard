import { useEffect, useRef, useState } from "react";
import { noiseChar } from "../lib/random.js";

const DURATION_MS = 600;
const reduceMotion = () =>
	window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Shows `value` when unlocked, or `cipher` (a ciphertext preview) when locked, and scrambles
// between the two when the vault locks or unlocks. Under reduced motion it just swaps.
export default function CiphertextText({ value, cipher = "", className = "" }) {
	const target = value ?? cipher;
	const [shown, setShown] = useState(target);
	const previous = useRef(target);

	useEffect(() => {
		if (previous.current === target) return;
		previous.current = target;
		if (reduceMotion()) {
			setShown(target);
			return;
		}
		const start = performance.now();
		let frame;
		const tick = (now) => {
			const progress = Math.min(1, (now - start) / DURATION_MS);
			const settled = Math.floor(progress * target.length);
			setShown(
				[...target]
					.map((ch, i) => (i < settled || ch === " " ? ch : noiseChar()))
					.join(""),
			);
			if (progress < 1) frame = requestAnimationFrame(tick);
		};
		frame = requestAnimationFrame(tick);
		return () => cancelAnimationFrame(frame);
	}, [target]);

	return (
		<span
			className={`${value == null ? "font-mono text-ink-3" : ""} ${className}`}
		>
			{shown}
		</span>
	);
}
