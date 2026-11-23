import { Upload, X } from "lucide-react";
import { useRef, useState } from "react";

const MAX_BYTES = 1024 * 1024;
const ALLOWED = [".csv", ".json"];

// Pre-checks only (size, extension). The browser never parses the file: the backend validates it.
export function precheck(file) {
	const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
	if (!ALLOWED.includes(ext)) return "Choose a .csv or .json file.";
	if (file.size > MAX_BYTES) return "That file is over 1 MB.";
	return "";
}

const formatSize = (bytes) =>
	bytes < 1024 ? `${bytes} B` : `${Math.round(bytes / 1024)} KB`;

// Click or drag-and-drop; keyboard reachable (the zone is a button that opens the file picker).
export default function FileDropZone({ file, onFile, error, disabled }) {
	const input = useRef(null);
	const [over, setOver] = useState(false);

	const take = (picked) => {
		if (picked) onFile(picked);
	};

	if (file) {
		return (
			<div className="flex items-center gap-3 rounded-[var(--radius-control)] border border-hairline bg-canvas px-3 py-2.5">
				<span className="min-w-0 flex-1 truncate text-sm font-medium">
					{file.name}
				</span>
				<span className="text-sm text-ink-2">{formatSize(file.size)}</span>
				<button
					type="button"
					onClick={() => onFile(null)}
					disabled={disabled}
					aria-label="Remove file"
					className="inline-flex size-8 items-center justify-center rounded-lg text-ink-2 hover:bg-black/5"
				>
					<X className="size-4" aria-hidden />
				</button>
			</div>
		);
	}

	return (
		<div>
			<button
				type="button"
				disabled={disabled}
				onClick={() => input.current?.click()}
				onDragOver={(e) => {
					e.preventDefault();
					setOver(true);
				}}
				onDragLeave={() => setOver(false)}
				onDrop={(e) => {
					e.preventDefault();
					setOver(false);
					take(e.dataTransfer.files?.[0]);
				}}
				className={`flex min-h-36 w-full flex-col items-center justify-center gap-2 rounded-[var(--radius-card)] border-2 border-dashed px-4 py-6 text-center transition-colors ${
					over
						? "border-ink bg-black/[0.04]"
						: "border-hairline hover:bg-black/[0.02]"
				}`}
			>
				<Upload className="size-6 text-ink-2" aria-hidden />
				<span className="text-sm font-medium">
					Drop a Chrome / Google CSV or a VaultGuard backup here
				</span>
				<span className="text-sm text-ink-2">
					or{" "}
					<span className="font-medium text-ink underline">choose a file</span>{" "}
					· .csv or .json · max 1 MB
				</span>
			</button>
			<input
				ref={input}
				type="file"
				accept=".csv,.json"
				className="sr-only"
				tabIndex={-1}
				onChange={(e) => {
					take(e.target.files?.[0]);
					e.target.value = ""; // picking the same file again should still fire
				}}
			/>
			{error && <p className="mt-2 text-sm text-danger">{error}</p>}
		</div>
	);
}
