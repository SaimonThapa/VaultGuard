import { ChevronDown } from "lucide-react";
import { daysSince } from "../../lib/format.js";
import Button from "../Button.jsx";
import CiphertextText from "../CiphertextText.jsx";
import HealthBadge from "../HealthBadge.jsx";
import LetterAvatar from "../LetterAvatar.jsx";
import EntryForm from "./EntryForm.jsx";
import SecretField from "./SecretField.jsx";

function Rotation({ entry }) {
	if (!entry.rotation_days) return <span className="text-ink-2">Not set</span>;
	const age = daysSince(entry.password_changed_at);
	if (entry.rotation_due) {
		return (
			<span className="text-warn">
				Overdue by {age - entry.rotation_days} days
			</span>
		);
	}
	return (
		<span>
			Every {entry.rotation_days} days · changed {age} days ago
		</span>
	);
}

// Accordion row. The whole header is one button; the panel shows details, a form, or ciphertext.
export default function PasswordRow({
	entry,
	badges = [],
	locked,
	open,
	editing,
	onToggle,
	onEdit,
	onDelete,
	onUnlock,
	onFormDone,
	onFormCancel,
	onDirtyChange,
}) {
	const panelId = `entry-${entry.id}`;
	const tampered = entry.integrity === "failed";
	const letterName = entry.site_name.trim() || "?";

	return (
		<li className="overflow-hidden rounded-[var(--radius-card)] border border-hairline bg-surface shadow-[var(--shadow-card)]">
			<button
				type="button"
				onClick={onToggle}
				aria-expanded={open}
				aria-controls={panelId}
				className="flex min-h-16 w-full items-center gap-3 px-4 py-3 text-left hover:bg-black/[0.02]"
			>
				<LetterAvatar name={letterName[0]} size={40} square />
				<span className="min-w-0 flex-1">
					<span className="block truncate font-medium">{entry.site_name}</span>
					<span className="block truncate text-sm text-ink-2">
						<CiphertextText
							value={entry.username}
							cipher={entry.ciphertext_preview}
						/>
					</span>
				</span>
				<span className="flex flex-wrap justify-end gap-1.5">
					{badges.map((kind) => (
						<HealthBadge key={kind} kind={kind} />
					))}
				</span>
				<ChevronDown
					className={`size-5 shrink-0 text-ink-3 transition-transform ${open ? "rotate-180" : ""}`}
					aria-hidden
				/>
			</button>

			{open && (
				<div id={panelId} className="border-t border-hairline">
					{editing ? (
						<EntryForm
							entry={entry}
							onDone={onFormDone}
							onCancel={onFormCancel}
							onDirtyChange={onDirtyChange}
						/>
					) : locked ? (
						<div className="p-4">
							<p className="mb-3 break-all rounded-[var(--radius-control)] bg-canvas p-3 font-mono text-sm text-ink-3">
								{entry.ciphertext_preview}…
							</p>
							<Button className="w-full" onClick={onUnlock}>
								Unlock to view
							</Button>
						</div>
					) : tampered ? (
						<div className="p-4">
							<p className="mb-3 rounded-[var(--radius-control)] bg-danger-bg p-3 text-sm text-danger">
								This entry failed its integrity check. Its data may have been
								tampered with and can't be shown.
							</p>
							<Button
								variant="danger-outline"
								className="w-full"
								onClick={onDelete}
							>
								Delete
							</Button>
						</div>
					) : (
						<div className="p-4">
							<div className="mb-4 rounded-[var(--radius-control)] border border-hairline px-3 py-1.5">
								<SecretField label="Username" value={entry.username} />
								<SecretField label="Password" value={entry.password} secret />
								<div className="flex items-center gap-3 py-1.5">
									<span className="w-24 shrink-0 text-sm text-ink-2">URL</span>
									<span className="min-w-0 flex-1 text-sm break-all">
										{entry.site_url ? (
											<a
												href={entry.site_url}
												target="_blank"
												rel="noopener noreferrer"
												className="underline"
											>
												{entry.site_url}
											</a>
										) : (
											<span className="text-ink-3">(none)</span>
										)}
									</span>
								</div>
								<div className="flex items-start gap-3 py-1.5">
									<span className="w-24 shrink-0 text-sm text-ink-2">
										Notes
									</span>
									<span className="min-w-0 flex-1 text-sm break-words whitespace-pre-wrap">
										{entry.notes || <span className="text-ink-3">(none)</span>}
									</span>
								</div>
								<div className="flex items-center gap-3 py-1.5 text-sm">
									<span className="w-24 shrink-0 text-ink-2">Rotation</span>
									<Rotation entry={entry} />
								</div>
							</div>
							<div className="grid grid-cols-2 gap-3">
								<Button variant="danger-outline" onClick={onDelete}>
									Delete
								</Button>
								<Button variant="secondary" onClick={onEdit}>
									Edit
								</Button>
							</div>
						</div>
					)}
				</div>
			)}
		</li>
	);
}
