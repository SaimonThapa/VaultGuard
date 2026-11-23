import { Copy, Download } from "lucide-react";
import { useToast } from "../context/ToastContext.jsx";
import Button from "./Button.jsx";

// Shows the recovery key once. The key lives only in component state, never in storage.
export default function RecoveryKeyCard({
	recoveryKey,
	username,
	checked,
	onChecked,
}) {
	const { toast } = useToast();

	const copy = async () => {
		try {
			await navigator.clipboard.writeText(recoveryKey);
			toast("Recovery key copied");
		} catch {
			toast("Couldn't copy. Select the key and copy it manually.", "error");
		}
	};

	const download = () => {
		const text = [
			"VaultGuard recovery key",
			"",
			`Account: ${username}`,
			`Saved: ${new Date().toLocaleDateString()}`,
			"",
			recoveryKey,
			"",
			"With an email code, this key is the only way to recover your vault if you forget your",
			"master key. Keep this file somewhere safe and private. It does not contain your master key.",
			"",
		].join("\n");
		const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
		const link = document.createElement("a");
		link.href = url;
		link.download = `vaultguard-recovery-key-${username}.txt`;
		link.click();
		URL.revokeObjectURL(url);
	};

	return (
		<div>
			<p
				data-testid="recovery-key"
				className="rounded-[var(--radius-control)] border border-hairline bg-surface px-4 py-5 text-center font-mono text-lg tracking-wider break-all select-all"
			>
				{recoveryKey}
			</p>
			<div className="mt-3 flex gap-2">
				<Button variant="secondary" onClick={copy}>
					<Copy className="size-4" aria-hidden /> Copy
				</Button>
				<Button variant="secondary" onClick={download}>
					<Download className="size-4" aria-hidden /> Download .txt
				</Button>
			</div>
			<label className="mt-5 flex items-start gap-2 text-sm">
				<input
					type="checkbox"
					checked={checked}
					onChange={(e) => onChecked(e.target.checked)}
					className="mt-0.5 size-4"
				/>
				I saved my recovery key somewhere safe.
			</label>
		</div>
	);
}
