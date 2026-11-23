import { Link } from "react-router";
import { bandFor } from "../../lib/bands.js";
import SegmentedBar from "../SegmentedBar.jsx";

// One checker: icon, name, one-line finding (+ Review link), 5-band bar, number, band label.
export default function CheckRow({
	icon: Icon,
	name,
	finding,
	review,
	metric,
}) {
	const band = bandFor(metric);
	return (
		<div className="grid items-center gap-x-4 gap-y-2 px-5 py-4 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_7rem]">
			<div className="flex min-w-0 items-start gap-3">
				<Icon className="mt-0.5 size-5 shrink-0 text-ink-2" aria-hidden />
				<div className="min-w-0">
					<p className="font-medium">{name}</p>
					<p className="text-sm text-ink-2">
						{finding}
						{review && (
							<>
								{" · "}
								<Link
									to={review}
									className="font-medium whitespace-nowrap text-ink underline"
								>
									Review →
								</Link>
							</>
						)}
					</p>
				</div>
			</div>
			<SegmentedBar metric={metric} label={name} />
			<p className="flex items-baseline gap-2 md:justify-end">
				<span className="text-xl font-semibold tabular-nums">
					{metric ?? "—"}
				</span>
				<span className="text-sm text-ink-2">{band.label}</span>
			</p>
		</div>
	);
}
