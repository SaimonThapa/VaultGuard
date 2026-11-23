import { Copy, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useToast } from "../context/ToastContext.jsx";
import { crockfordKey } from "../lib/random.js";
import { MIN_SCORE, strengthOf } from "../lib/strength.js";
import Button from "./Button.jsx";
import CrackMeter from "./CrackMeter.jsx";
import PasswordField from "./PasswordField.jsx";

// The signup 3a block, reused by recovery, reset and "change master key":
// generator, crack-time meter, confirm field. Rules mirror the backend (12-256 chars, score >= 3).
export function masterKeyReady(key, confirm) {
	return (
		key.length >= 12 &&
		key.length <= 256 &&
		strengthOf(key).score >= MIN_SCORE &&
		confirm === key
	);
}

export default function MasterKeyFields({
	value,
	confirm,
	onValue,
	onConfirm,
	serverError,
}) {
	const { toast } = useToast();
	const [example] = useState(() => crockfordKey(128)); // grey hint only; the field starts empty
	const [reveal, setReveal] = useState(0);

	const strength = value ? strengthOf(value) : null;
	const problem = serverError
		? serverError
		: value && (value.length < 12 || value.length > 256)
			? "Use 12–256 characters."
			: strength && strength.score < MIN_SCORE
				? "Choose a stronger key."
				: confirm && confirm !== value
					? "The keys don't match."
					: "";

	const generate = (bits) => {
		const next = crockfordKey(bits);
		onValue(next);
		onConfirm(next); // no retyping a long random key; the user is told to copy it
		setReveal((n) => n + 1);
	};

	const copy = async () => {
		try {
			await navigator.clipboard.writeText(value);
			toast("Master key copied. Save it somewhere safe.");
		} catch {
			toast("Couldn't copy. Select the key and copy it manually.", "error");
		}
	};

	return (
		<div>
			<PasswordField
				label="Master key"
				value={value}
				onChange={(e) => onValue(e.target.value)}
				placeholder={example}
				error={problem}
				autoComplete="off"
				spellCheck={false}
				revealToken={reveal}
				className="mb-3 [&_input]:font-mono"
			/>
			<div className="mb-2 flex flex-wrap gap-2">
				<Button variant="secondary" onClick={() => generate(128)}>
					<RefreshCw className="size-4" aria-hidden /> Generate 128-bit
				</Button>
				<Button variant="secondary" onClick={() => generate(256)}>
					<RefreshCw className="size-4" aria-hidden /> 256-bit
				</Button>
				<Button variant="secondary" onClick={copy} disabled={!value}>
					<Copy className="size-4" aria-hidden /> Copy
				</Button>
			</div>
			<p className="mb-4 text-sm text-ink-2">
				Recommended: a generated 128-bit or 256-bit key.
			</p>
			<div className="mb-4">
				<CrackMeter guessesLog10={strength?.guessesLog10} />
			</div>
			<PasswordField
				label="Confirm master key"
				value={confirm}
				onChange={(e) => onConfirm(e.target.value)}
				autoComplete="off"
				spellCheck={false}
				revealToken={reveal}
				className="[&_input]:font-mono"
			/>
		</div>
	);
}
