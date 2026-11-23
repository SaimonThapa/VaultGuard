import { bandFor } from "../lib/bands.js";
import { crackTime } from "../lib/format.js";

// Attacker assumptions printed under the meter (architecture.md §7): a GPU rig.
const ARGON2_RATE = 1e4;
const FAST_HASH_RATE = 1e10;

// Same formula as the backend's master_key metric: min(100, guesses_log10 x 5).
const metricFor = (log10) => Math.max(0, Math.min(100, Math.round(log10 * 5)));

function Row({ label, log10, rate }) {
	const metric = metricFor(log10 - Math.log10(rate / ARGON2_RATE));
	const band = bandFor(metric);
	return (
		<div className="mb-3 last:mb-0">
			<div className="mb-1 flex items-baseline justify-between gap-2 text-sm">
				<span>{label}</span>
				<span className="font-medium">
					{crackTime(log10, rate)}{" "}
					<span className="text-ink-2">· {band.label}</span>
				</span>
			</div>
			<div className="h-2 overflow-hidden rounded-full bg-black/[0.08]">
				<div
					className="h-full rounded-full transition-[width] duration-500 ease-out"
					style={{ width: `${Math.max(metric, 3)}%`, background: band.color }}
				/>
			</div>
		</div>
	);
}

// "How long to crack": Argon2id (what VaultGuard uses) next to a plain fast hash.
export default function CrackMeter({ guessesLog10 }) {
	if (guessesLog10 == null) return null;
	return (
		<div className="rounded-[var(--radius-control)] border border-hairline bg-surface/60 p-4">
			<p className="mb-3 text-sm font-medium">How long to crack</p>
			<Row
				label="With Argon2id (VaultGuard)"
				log10={guessesLog10}
				rate={ARGON2_RATE}
			/>
			<Row
				label="With a plain fast hash"
				log10={guessesLog10}
				rate={FAST_HASH_RATE}
			/>
			<p className="mt-3 text-xs text-ink-3">
				Assumes an attacker GPU rig making 10⁴ guesses per second against
				Argon2id and 10¹⁰ against a fast hash.
			</p>
		</div>
	);
}
