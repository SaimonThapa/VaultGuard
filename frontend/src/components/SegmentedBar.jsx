import { bandFor } from "../lib/bands.js";

// The 5-band bar with a pointer at the metric. Widths follow the score ranges, so the pointer's
// position and the segment it sits on always agree. Unavailable renders a grey striped bar.
const SEGMENTS = [
	[0, 40],
	[40, 60],
	[60, 75],
	[75, 90],
	[90, 100],
];

export default function SegmentedBar({ metric, label }) {
	const known = metric != null;
	const band = bandFor(metric);
	return (
		// biome-ignore lint/a11y/useSemanticElements: custom-drawn meter, <meter> can't be styled this way
		<div
			role="meter"
			aria-label={label}
			aria-valuemin={0}
			aria-valuemax={100}
			aria-valuenow={known ? metric : undefined}
			aria-valuetext={known ? `${metric}, ${band.label}` : "Unavailable"}
			className="relative w-full pt-2.5"
		>
			{known && (
				<span
					aria-hidden
					className="absolute top-0 size-0 -translate-x-1/2 border-x-[5px] border-t-[7px] border-x-transparent border-t-ink transition-[left] duration-700 ease-out"
					style={{ left: `${metric}%` }}
				/>
			)}
			<div className="flex h-2.5 gap-0.5">
				{SEGMENTS.map(([from, to]) => (
					<span
						key={from}
						className="rounded-full"
						style={{
							width: `${to - from}%`,
							background: known ? bandFor(from).color : "rgb(0 0 0 / 0.1)",
							backgroundImage: known
								? undefined
								: "repeating-linear-gradient(135deg, transparent 0 4px, rgb(255 255 255 / 0.7) 4px 6px)",
						}}
					/>
				))}
			</div>
		</div>
	);
}
