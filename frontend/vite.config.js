import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
	plugins: [react(), tailwindcss()],
	server: {
		// Proxy API calls to FastAPI so the browser sees a single origin in dev.
		proxy: {
			"/api": process.env.API_TARGET ?? "http://127.0.0.1:8000",
		},
	},
});
