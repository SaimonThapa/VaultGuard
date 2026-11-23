import { RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useToast } from "../../context/ToastContext.jsx";
import { api } from "../../lib/api.js";
import { crackTime } from "../../lib/format.js";
import { strengthOf } from "../../lib/strength.js";
import Button from "../Button.jsx";
import PasswordField, { StrengthHint } from "../PasswordField.jsx";
import TextField from "../TextField.jsx";
import PasswordGenerator from "./PasswordGenerator.jsx";

const ROTATIONS = [
	["", "Off"],
	["30", "Every 30 days"],
	["60", "Every 60 days"],
	["90", "Every 90 days"],
	["180", "Every 180 days"],
	["365", "Every 365 days"],
];

function initialValues(entry) {
	return {
		site_name: entry?.site_name ?? "",
		site_url: entry?.site_url ?? "",
		username: entry?.username ?? "",
		password: entry?.password ?? "",
		notes: entry?.notes ?? "",
		rotation_days: entry?.rotation_days ? String(entry.rotation_days) : "",
	};
}

// Add or edit one entry, inline. onDone(saved) after success; onCancel() to close.
export default function EntryForm({ entry, onDone, onCancel, onDirtyChange }) {
	const { toast } = useToast();
	const [values, setValues] = useState(() => initialValues(entry));
	const [errors, setErrors] = useState({});
	const [busy, setBusy] = useState(false);
	const [showGenerator, setShowGenerator] = useState(false);
	const first = useRef(null);
	const original = useRef(initialValues(entry));

	useEffect(() => first.current?.focus(), []);
	const dirty = JSON.stringify(values) !== JSON.stringify(original.current);
	useEffect(() => onDirtyChange?.(dirty), [dirty, onDirtyChange]);

	const set = (key) => (e) =>
		setValues((v) => ({ ...v, [key]: e.target.value }));
	const strength = values.password ? strengthOf(values.password) : null;
	const invalid =
		!values.site_name.trim() ||
		values.site_name.length > 100 ||
		!values.password ||
		values.password.length > 256 ||
		values.username.length > 256 ||
		values.notes.length > 2000;

	const submit = async (e) => {
		e.preventDefault();
		if (invalid) return;
		setBusy(true);
		setErrors({});
		const body = {
			site_name: values.site_name.trim(),
			site_url: values.site_url.trim() || null,
			username: values.username,
			password: values.password,
			notes: values.notes || null,
			rotation_days: values.rotation_days ? Number(values.rotation_days) : null,
		};
		try {
			const saved = await api(
				entry ? `/api/entries/${entry.id}` : "/api/entries",
				{
					method: entry ? "PUT" : "POST",
					body,
					toast: false,
				},
			);
			toast("Saved");
			onDone(saved);
		} catch (err) {
			if (err.status === 422) {
				setErrors(
					Object.fromEntries(
						(err.body.fields ?? []).map((f) => [f, "Check this field."]),
					),
				);
				toast(err.message, "error");
			} else if (err.status !== 423) {
				toast(err.message, "error"); // 423 opens the unlock modal instead
			}
		} finally {
			setBusy(false);
		}
	};

	return (
		<form
			onSubmit={submit}
			onKeyDown={(e) => e.key === "Escape" && onCancel()}
			noValidate
			className="grid gap-4 p-4"
		>
			<TextField
				label="Site"
				value={values.site_name}
				onChange={set("site_name")}
				error={errors.site_name}
				maxLength={100}
				ref={first}
				required
			/>
			<TextField
				label="URL"
				value={values.site_url}
				onChange={set("site_url")}
				error={errors.site_url}
				hint="youtube.com works; https:// is added for you."
				autoComplete="off"
			/>
			<TextField
				label="Username"
				value={values.username}
				onChange={set("username")}
				error={errors.username}
				autoComplete="off"
			/>
			<div>
				<PasswordField
					label="Password"
					value={values.password}
					onChange={set("password")}
					error={errors.password}
					autoComplete="new-password"
					spellCheck={false}
				/>
				<div className="mt-1.5 flex items-center gap-2">
					<Button
						variant="ghost"
						className="min-h-8 px-2"
						onClick={() => setShowGenerator((s) => !s)}
						aria-expanded={showGenerator}
					>
						<RefreshCw className="size-4" aria-hidden /> Generate
					</Button>
					{strength && (
						<span className="text-sm text-ink-2">
							{crackTime(strength.guessesLog10, 1e10)} to crack
						</span>
					)}
				</div>
				{showGenerator && (
					<PasswordGenerator
						onGenerate={(pw) => setValues((v) => ({ ...v, password: pw }))}
					/>
				)}
				<StrengthHint strength={strength} />
			</div>
			<div>
				<label
					htmlFor="entry-notes"
					className="mb-1.5 block text-sm font-medium"
				>
					Notes
				</label>
				<textarea
					id="entry-notes"
					value={values.notes}
					onChange={set("notes")}
					rows={3}
					maxLength={2000}
					className="w-full rounded-[var(--radius-control)] border border-hairline bg-surface px-3 py-2 text-[15px]"
				/>
				{values.notes.length > 1800 && (
					<p className="mt-1 text-sm text-ink-2">
						{values.notes.length} / 2000
					</p>
				)}
			</div>
			<div>
				<label
					htmlFor="entry-rotation"
					className="mb-1.5 block text-sm font-medium"
				>
					Rotation reminder
				</label>
				<select
					id="entry-rotation"
					value={values.rotation_days}
					onChange={set("rotation_days")}
					className="h-10 w-full rounded-[var(--radius-control)] border border-hairline bg-surface px-3 text-[15px]"
				>
					{ROTATIONS.map(([value, label]) => (
						<option key={value} value={value}>
							{label}
						</option>
					))}
				</select>
			</div>
			<div className="flex justify-end gap-2">
				<Button variant="secondary" onClick={onCancel}>
					Cancel
				</Button>
				<Button
					type="submit"
					variant="create"
					loading={busy}
					disabled={invalid}
				>
					{entry ? "Save" : "Add"}
				</Button>
			</div>
		</form>
	);
}
