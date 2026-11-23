import { useState } from "react";
import { generatePassword } from "../../lib/random.js";
import Button from "../Button.jsx";

const SETS = [
	["upper", "A–Z"],
	["lower", "a–z"],
	["digits", "0–9"],
	["symbols", "Symbols"],
];

// Panel under the password field. Calls onGenerate(password); at least one set stays on.
export default function PasswordGenerator({ onGenerate }) {
	const [length, setLength] = useState(20);
	const [sets, setSets] = useState({
		upper: true,
		lower: true,
		digits: true,
		symbols: true,
	});

	const toggle = (key) => {
		const next = { ...sets, [key]: !sets[key] };
		if (Object.values(next).some(Boolean)) setSets(next);
	};

	return (
		<div className="mt-2 rounded-[var(--radius-control)] border border-hairline bg-canvas p-3">
			<label className="flex items-center gap-3 text-sm">
				<span className="w-16">Length {length}</span>
				<input
					type="range"
					min={8}
					max={64}
					value={length}
					onChange={(e) => setLength(Number(e.target.value))}
					className="flex-1"
				/>
			</label>
			<div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
				{SETS.map(([key, label]) => (
					<label key={key} className="flex items-center gap-1.5 text-sm">
						<input
							type="checkbox"
							checked={sets[key]}
							onChange={() => toggle(key)}
						/>
						{label}
					</label>
				))}
			</div>
			<Button
				variant="secondary"
				className="mt-3"
				onClick={() => onGenerate(generatePassword({ length, ...sets }))}
			>
				Generate password
			</Button>
		</div>
	);
}
