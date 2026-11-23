import { useEffect, useState } from "react";
import { bandFor } from "../../lib/bands.js";

// Semicircle gauge: 5 band segments (sized by score range), a marker that sweeps to the score,
// and the big number + band label in the hollow. Pure SVG.
const CX = 120;
const CY = 120;
const R = 94;
const BANDS = [
	[0, 40],
	[40, 60],
	[60, 75],
	[75, 90],
	[90, 100],
];
const GAP = 0.7; // score units: about 2 px between segments

const point = (t, r = R) => {
	const angle = Math.PI * (1 - t / 100);
	return [CX + r * Math.cos(angle), CY - r * Math.sin(angle)];
};
const arc = (from, to) => {
	const [x0, y0] = point(from);
	const [x1, y1] = point(to);
	return `M ${x0} ${y0} A ${R} ${R} 0 0 1 ${x1} ${y1}`;
};

export default function HealthGauge({ score }) {
	const known = score != null;
	const band = bandFor(score);
	const [shown, setShown] = useState(0);

	// Sweep from 0 on load and on every new score (instant under reduced motion, via the CSS).
	useEffect(() => {
		setShown(0);
		const frame = requestAnimationFrame(() => setShown(known ? score : 0));
		return () => cancelAnimationFrame(frame);
	}, [score, known]);

	return (
		// biome-ignore lint/a11y/useSemanticElements: custom-drawn meter, <meter> can't be styled this way
		<div
			role="meter"
			aria-label="Overall health"
			aria-valuemin={0}
			aria-valuemax={100}
			aria-valuenow={known ? score : undefined}
			aria-valuetext={known ? `${score}, ${band.label}` : "Not available"}
			className="mx-auto w-full max-w-[420px]"
		>
			<svg viewBox="0 0 240 150" className="w-full" aria-hidden="true">
				{BANDS.map(([from, to]) => (
					<path
						key={from}
						d={arc(
							from + (from === 0 ? 0 : GAP / 2),
							to - (to === 100 ? 0 : GAP / 2),
						)}
						fill="none"
						strokeWidth="16"
						stroke={known ? bandFor(from).color : "rgb(0 0 0 / 0.1)"}
						opacity={known ? 1 : 0.9}
					/>
				))}
				{known && (
					<g
						style={{
							transformOrigin: `${CX}px ${CY}px`,
							transform: `rotate(${(shown / 100) * 180}deg)`,
							transition: "transform 700ms var(--ease-out)",
						}}
					>
						<polygon
							points={`${CX - R - 24},${CY - 7} ${CX - R - 10},${CY} ${CX - R - 24},${CY + 7}`}
							fill="var(--color-ink)"
						/>
					</g>
				)}
				<text
					x={CX}
					y={CY - 16}
					textAnchor="middle"
					className="fill-ink"
					style={{ fontSize: 52, fontWeight: 600, letterSpacing: "-0.02em" }}
				>
					{known ? score : "—"}
				</text>
				<text
					x={CX}
					y={CY + 10}
					textAnchor="middle"
					className="fill-ink-2"
					style={{ fontSize: 15 }}
				>
					{band.label}
				</text>
			</svg>
		</div>
	);
}
