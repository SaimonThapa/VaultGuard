import { useCallback, useEffect, useState } from "react";

// Counts whole seconds down to 0. start(n) restarts it (resend timers, Retry-After lockouts).
export function useCountdown(initial = 0) {
	const [left, setLeft] = useState(initial);
	useEffect(() => {
		if (left <= 0) return;
		const timer = setTimeout(() => setLeft((n) => n - 1), 1000);
		return () => clearTimeout(timer);
	}, [left]);
	const start = useCallback((seconds) => setLeft(seconds), []);
	return [left, start];
}

export function clock(seconds) {
	return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}
