// A glass card centered over greyed-out content, for visitor / locked / not-set-up states.
export default function StateOverlay({ title, children, actions }) {
	return (
		<div className="pointer-events-none absolute inset-0 z-10 flex items-start justify-center p-4 pt-24">
			<div className="glass pointer-events-auto w-full max-w-sm rounded-[var(--radius-sheet)] p-6 text-center shadow-[var(--shadow-float)]">
				<p className="mb-1 text-lg font-semibold">{title}</p>
				{children && <p className="mb-4 text-sm text-ink-2">{children}</p>}
				<div className="flex flex-wrap justify-center gap-2">{actions}</div>
			</div>
		</div>
	);
}
