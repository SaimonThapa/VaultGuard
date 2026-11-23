import { ShieldCheck } from "lucide-react";
import { Link } from "react-router";

export default function Logo({ className = "" }) {
	return (
		<Link
			to="/"
			className={`inline-flex items-center gap-2 font-semibold ${className}`}
		>
			<span className="inline-flex size-8 items-center justify-center rounded-[10px] bg-ink text-white">
				<ShieldCheck className="size-[18px]" aria-hidden />
			</span>
			VaultGuard
		</Link>
	);
}
