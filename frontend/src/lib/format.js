// Only internal paths ("/x", not "//x" or "http://...") are followed after login: no open redirect.
export function safeNext(next) {
	return typeof next === "string" &&
		next.startsWith("/") &&
		!next.startsWith("//")
		? next
		: "/";
}

export function initials(name = "") {
	return name.slice(0, 2).toUpperCase() || "?";
}

const SUPERSCRIPT = "⁰¹²³⁴⁵⁶⁷⁸⁹";
const superscript = (n) => [...String(n)].map((d) => SUPERSCRIPT[d]).join("");

// Average time to crack = half the guesses at the attacker's rate (guesses/second).
export function crackTime(guessesLog10, ratePerSecond) {
	const log10Seconds = guessesLog10 - Math.log10(2 * ratePerSecond);
	if (log10Seconds < 0) return "under a second";
	if (log10Seconds >= 15) {
		return `~10${superscript(Math.round(log10Seconds - Math.log10(31557600)))} years`;
	}
	const seconds = 10 ** log10Seconds;
	const steps = [
		[60, "second"],
		[3600, "minute"],
		[86400, "hour"],
		[31557600, "day"],
	];
	let divisor = 1;
	for (const [limit, unit] of steps) {
		if (seconds < limit) {
			const n = Math.max(1, Math.round(seconds / divisor));
			return `~${n} ${unit}${n === 1 ? "" : "s"}`;
		}
		divisor = limit;
	}
	const years = Math.round(seconds / 31557600);
	return `~${years.toLocaleString()} year${years === 1 ? "" : "s"}`;
}

export function daysSince(iso) {
	return Math.max(
		0,
		Math.floor((Date.now() - new Date(iso).getTime()) / 86400000),
	);
}

// "just now", "2 min ago", "3 hours ago" for an ISO timestamp.
export function timeAgo(iso) {
	const minutes = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
	if (minutes < 1) return "just now";
	if (minutes < 60) return `${minutes} min ago`;
	const hours = Math.floor(minutes / 60);
	return hours < 24
		? `${hours} hour${hours === 1 ? "" : "s"} ago`
		: `${Math.floor(hours / 24)} days ago`;
}

// "~10^20 years" (backend text) -> "~10²⁰ years", same look as the signup crack meter.
export function superscriptPowers(text) {
	return text.replace(/10\^(\d+)/g, (_, n) => `10${superscript(n)}`);
}

// "Today", "Yesterday" or "Nov 20" (with the year when it isn't this year), in local time.
export function dayLabel(iso) {
	const date = new Date(iso);
	const startOfDay = (d) =>
		new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
	const diffDays = Math.round(
		(startOfDay(new Date()) - startOfDay(date)) / 86400000,
	);
	if (diffDays === 0) return "Today";
	if (diffDays === 1) return "Yesterday";
	const sameYear = date.getFullYear() === new Date().getFullYear();
	return date.toLocaleDateString([], {
		month: "short",
		day: "numeric",
		...(sameYear ? {} : { year: "numeric" }),
	});
}
