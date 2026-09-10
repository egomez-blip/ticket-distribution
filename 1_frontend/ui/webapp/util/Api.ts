import Config from "./Config";

/**
 * Wrapper de fetch que añade el token JWT (Authorization: Bearer) desde
 * sessionStorage y centraliza el manejo de errores/JSON.
 */
export default class Api {
	static getToken(): string | null {
		return sessionStorage.getItem(Config.TOKEN_KEY);
	}

	static setSession(token: string, user: object): void {
		sessionStorage.setItem(Config.TOKEN_KEY, token);
		sessionStorage.setItem(Config.USER_KEY, JSON.stringify(user));
	}

	static getUser(): { id: number; email: string; username: string; role: string } | null {
		const raw = sessionStorage.getItem(Config.USER_KEY);
		return raw ? JSON.parse(raw) : null;
	}

	static clear(): void {
		sessionStorage.removeItem(Config.TOKEN_KEY);
		sessionStorage.removeItem(Config.USER_KEY);
	}

	private static headers(json = true): Record<string, string> {
		const h: Record<string, string> = {};
		if (json) { h["Content-Type"] = "application/json"; }
		const token = Api.getToken();
		if (token) { h["Authorization"] = `Bearer ${token}`; }
		return h;
	}

	private static async handle(res: Response): Promise<any> {
		if (res.status === 204) { return null; }
		const text = await res.text();
		const data = text ? JSON.parse(text) : null;
		if (!res.ok) {
			const detail = (data && data.detail) || res.statusText;
			throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
		}
		return data;
	}

	static async get(path: string): Promise<any> {
		return Api.handle(await fetch(`${Config.API_BASE}${path}`, { headers: Api.headers(false) }));
	}

	static async post(path: string, body?: object): Promise<any> {
		return Api.handle(await fetch(`${Config.API_BASE}${path}`, {
			method: "POST", headers: Api.headers(), body: body ? JSON.stringify(body) : undefined
		}));
	}

	static async put(path: string, body: object): Promise<any> {
		return Api.handle(await fetch(`${Config.API_BASE}${path}`, {
			method: "PUT", headers: Api.headers(), body: JSON.stringify(body)
		}));
	}

	static async patch(path: string, body: object): Promise<any> {
		return Api.handle(await fetch(`${Config.API_BASE}${path}`, {
			method: "PATCH", headers: Api.headers(), body: JSON.stringify(body)
		}));
	}

	static async del(path: string): Promise<any> {
		return Api.handle(await fetch(`${Config.API_BASE}${path}`, {
			method: "DELETE", headers: Api.headers(false)
		}));
	}

	/** Sube un archivo (multipart/form-data). No fija Content-Type: el navegador pone el boundary. */
	static async upload(path: string, file: File): Promise<any> {
		const fd = new FormData();
		fd.append("file", file);
		const h = Api.headers(false);
		return Api.handle(await fetch(`${Config.API_BASE}${path}`, {
			method: "POST", headers: h, body: fd
		}));
	}
}

export class ApiError extends Error {
	public status: number;
	constructor(status: number, message: string) {
		super(message);
		this.status = status;
	}
}
