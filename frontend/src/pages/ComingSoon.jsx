// Placeholder for pages built in later phases (architecture.md §14). Each gets replaced by its page.
export default function ComingSoon({ title }) {
	return (
		<div>
			<h1 className="text-2xl font-semibold">{title}</h1>
			<p className="mt-1 text-ink-2">This page is built in a later phase.</p>
		</div>
	);
}
