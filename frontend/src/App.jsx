import { useEffect, useState } from "react";

// Placeholder page: confirms the frontend can reach the backend through the Vite proxy.
export default function App() {
	const [status, setStatus] = useState("checking…");

	useEffect(() => {
		fetch("/api/health")
			.then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
			.then((data) => setStatus(`api: ${data.status}, db: ${data.db}`))
			.catch(() => setStatus("backend unreachable"));
	}, []);

	return (
		<main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-900 text-slate-100">
			<h1 className="text-4xl font-bold">VaultGuard</h1>
			<p className="rounded bg-slate-800 px-4 py-2 font-mono text-sm">
				{status}
			</p>
		</main>
	);
}
