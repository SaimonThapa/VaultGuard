// fetch wrapper: attaches the access token, refreshes once on 401 (never for /api/auth/*),
// opens the unlock modal on 423, and toasts the server's generic message on other errors.

let accessToken = null;
const hooks = {
	refresh: async () => false, // set by AuthContext: restores a session from the cookie
	onSessionLost: () => {}, // refresh failed: toast + go to login
	onLocked: () => {}, // 423: open the unlock modal
	toast: () => {},
};

export function configureApi(next) {
	Object.assign(hooks, next);
}
export function setAccessToken(token) {
	accessToken = token;
}

export class ApiError extends Error {
	constructor(status, body) {
		super(body?.message || "Something went wrong.");
		this.status = status;
		this.code = body?.error || "error";
		this.body = body || {};
	}
}

async function send(path, { method = "GET", body, form }) {
	const headers = {};
	if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
	let payload;
	if (form) {
		payload = form; // the browser sets the multipart boundary
	} else if (body !== undefined) {
		headers["Content-Type"] = "application/json";
		payload = JSON.stringify(body);
	}
	return fetch(path, {
		method,
		headers,
		body: payload,
		credentials: "include",
	});
}

export async function api(path, options = {}) {
	const { toast = true, raw = false } = options;
	let res;
	try {
		res = await send(path, options);
	} catch {
		const err = new ApiError(0, {
			error: "network",
			message: "Can't reach the server.",
		});
		if (toast) hooks.toast(err.message, "error");
		throw err;
	}

	if (res.status === 401 && !path.startsWith("/api/auth/")) {
		if (await hooks.refresh()) {
			res = await send(path, options);
		}
		if (res.status === 401) {
			hooks.onSessionLost();
			throw new ApiError(401, {
				error: "unauthorized",
				message: "Please log in again.",
			});
		}
	}

	if (res.ok) {
		if (raw) return res;
		return res.status === 204 ? null : res.json();
	}

	const err = new ApiError(res.status, await res.json().catch(() => null));
	err.retryAfter = Number(res.headers.get("Retry-After")) || null;
	if (res.status === 423) hooks.onLocked();
	else if (toast) hooks.toast(err.message, "error");
	throw err;
}
