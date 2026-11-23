import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import "./index.css";
import App from "./App.jsx";
import { AuthProvider } from "./context/AuthContext.jsx";
import { HealthProvider } from "./context/HealthContext.jsx";
import { ToastProvider } from "./context/ToastContext.jsx";
import { UnlockModalProvider } from "./context/UnlockModalContext.jsx";

createRoot(document.getElementById("root")).render(
	<StrictMode>
		<BrowserRouter>
			<ToastProvider>
				<UnlockModalProvider>
					<AuthProvider>
						<HealthProvider>
							<App />
						</HealthProvider>
					</AuthProvider>
				</UnlockModalProvider>
			</ToastProvider>
		</BrowserRouter>
	</StrictMode>,
);
