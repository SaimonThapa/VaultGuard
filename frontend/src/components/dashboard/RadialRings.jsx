import { useEffect, useState } from "react";
import { bandFor } from "../../lib/bands.js";

// Three concentric rings, outer to inner: Weak, Breached, Reused. Each fills clockwise to its
// 0-100 metric (the same number as its row in Security checks) over a light track.
// One hue per ring (a validated categorical palette), so the rings don't all read as "green".
// Identity comes from position, the legend label and the number; the hue is only a helper.
const RINGS = [
	{ key: "weak", label: "Weak", radius: 82, color: "#2F6FDE" },
	{ key: "breach", label: "Breached", radius: 62, color: "#0F9D8A" },
	{ key: "reused", label: "Reused", radius: 42, color: "#8B4FD1" },
];
const STROKE = 12;

export default function RadialRings({ values }) {
	// values: { crack, breach, reused } metrics (null = unavailable/unknown)
	const [shown, setShown] = useState({});
	const signature = JSON.stringify(values);
	const anyKnown = Object.values(values).some((v) => v != null);

	// biome-ignore lint/correctness/useExhaustiveDependencies: signature captures values
	useEffect(() => {
		setShown({});
		const frame = requestAnimationFrame(() => setShown(values));
		return () => cancelAnimationFrame(frame);
	}, [signature]);

	return (
		<div>
			<svg
				viewBox="0 0 200 200"
				className="mx-auto w-full max-w-[240px]"
				role="img"
				aria-label={RINGS.map(
					(r) =>
						`${r.label} ${values[r.key] == null ? "unavailable" : values[r.key]}`,
				).join(", ")}
			>
				{RINGS.map(({ key, radius, color }) => {
					const metric = values[key];
					const circumference = 2 * Math.PI * radius;
					const filled = ((shown[key] ?? 0) / 100) * circumference;
					return (
						<g key={key} transform="rotate(-90 100 100)">
							<circle
								cx="100"
								cy="100"
								r={radius}
								fill="none"
								stroke="rgb(0 0 0 / 0.08)"
								strokeWidth={STROKE}
								strokeDasharray={
									metric == null && key === "breach" && anyKnown
										? "2 7"
										: undefined
								}
							/>
							{metric != null && (
								<circle
									cx="100"
									cy="100"
									r={radius}
									fill="none"
									stroke={color}
									strokeWidth={STROKE}
									strokeLinecap="round"
									strokeDasharray={`${filled} ${circumference}`}
									style={{
										transition: "stroke-dasharray 700ms var(--ease-out)",
									}}
								/>
							)}
						</g>
					);
				})}
			</svg>
			<ul className="mt-3 flex flex-wrap justify-center gap-x-4 gap-y-1 text-sm">
				{RINGS.map(({ key, label, color }) => {
					const metric = values[key];
					return (
						<li
							key={key}
							className="flex items-center gap-1.5"
							title={
								metric == null
									? `${label} check unavailable`
									: `${label}: ${bandFor(metric).label}`
							}
						>
							<span
								aria-hidden
								className="size-2.5 rounded-full"
								style={{
									background: metric == null ? "var(--color-ink-3)" : color,
								}}
							/>
							{label} <span className="font-medium">{metric ?? "—"}</span>
						</li>
					);
				})}
			</ul>
		</div>
	);
}
