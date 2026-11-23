// The one 5-band scale shared by the gauge, rings, bars and badges (design.md §1.1).
const BANDS = [
	{
		key: "critical",
		label: "Critical",
		min: 0,
		color: "var(--color-band-critical)",
	},
	{ key: "poor", label: "Poor", min: 40, color: "var(--color-band-poor)" },
	{ key: "fair", label: "Fair", min: 60, color: "var(--color-band-fair)" },
	{ key: "good", label: "Good", min: 75, color: "var(--color-band-good)" },
	{
		key: "excellent",
		label: "Excellent",
		min: 90,
		color: "var(--color-band-excellent)",
	},
];

export function bandFor(score) {
	if (score == null) {
		return {
			key: "unavailable",
			label: "Unavailable",
			color: "var(--color-ink-3)",
		};
	}
	return [...BANDS].reverse().find((b) => score >= b.min);
}
