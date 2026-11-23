import { createContext, useContext, useMemo, useState } from "react";

// Lets any component (or the api client) open the unlock modal. The modal itself is built in
// phase 3 (design.md §6.1).
const UnlockModalContext = createContext(null);
export const useUnlockModal = () => useContext(UnlockModalContext);

export function UnlockModalProvider({ children }) {
	const [open, setOpen] = useState(false);
	const value = useMemo(
		() => ({
			open,
			openUnlock: () => setOpen(true),
			closeUnlock: () => setOpen(false),
		}),
		[open],
	);
	return (
		<UnlockModalContext.Provider value={value}>
			{children}
		</UnlockModalContext.Provider>
	);
}
