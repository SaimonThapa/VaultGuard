import { Check } from "lucide-react";

// "1 Account - 2 Verify - 3 Master key". Done steps get a check; the current one is bold.
export default function StepIndicator({ steps, current }) {
	return (
		<ol className="mb-6 flex items-center gap-2 text-sm" aria-label="Progress">
			{steps.map((label, i) => {
				const done = i < current;
				return (
					<li
						key={label}
						aria-current={i === current ? "step" : undefined}
						className={`flex items-center gap-2 ${i === current ? "font-semibold" : "text-ink-2"}`}
					>
						<span
							className={`inline-flex size-5 items-center justify-center rounded-full text-xs ${
								done || i === current ? "bg-ink text-white" : "bg-black/[0.08]"
							}`}
						>
							{done ? <Check className="size-3" aria-hidden /> : i + 1}
						</span>
						{label}
						{i < steps.length - 1 && (
							<span aria-hidden className="h-px w-4 bg-hairline" />
						)}
					</li>
				);
			})}
		</ol>
	);
}
