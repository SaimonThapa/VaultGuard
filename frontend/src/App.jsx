import { Route, Routes } from "react-router";
import UnlockModal from "./components/UnlockModal.jsx";
import AppShell from "./layouts/AppShell.jsx";
import AuthLayout from "./layouts/AuthLayout.jsx";
import Activity from "./pages/Activity.jsx";
import ComingSoon from "./pages/ComingSoon.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import ForgotPassword from "./pages/ForgotPassword.jsx";
import Login from "./pages/Login.jsx";
import Passwords from "./pages/Passwords.jsx";
import RecoverMasterKey from "./pages/RecoverMasterKey.jsx";
import ResetVault from "./pages/ResetVault.jsx";
import Settings from "./pages/Settings.jsx";
import Signup from "./pages/Signup.jsx";
import Transfer from "./pages/Transfer.jsx";

// Route table. Visitors may open "/" only; AppShell redirects everything else to /login?next=.
export default function App() {
	return (
		<>
			<Routes>
				<Route element={<AppShell />}>
					<Route index element={<Dashboard />} />
					<Route path="passwords" element={<Passwords />} />
					<Route path="transfer" element={<Transfer />} />
					<Route path="activity" element={<Activity />} />
					<Route path="settings" element={<Settings />} />
				</Route>
				<Route element={<AuthLayout guestOnly />}>
					<Route path="forgot-password" element={<ForgotPassword />} />
				</Route>
				<Route element={<AuthLayout />}>
					<Route path="login" element={<Login />} />
					<Route path="signup" element={<Signup />} />
					<Route path="recover-master-key" element={<RecoverMasterKey />} />
					<Route path="reset-vault" element={<ResetVault />} />
				</Route>
				<Route path="*" element={<ComingSoon title="Page not found" />} />
			</Routes>
			<UnlockModal />
		</>
	);
}
