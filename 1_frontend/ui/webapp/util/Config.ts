/**
 * Configuración central del frontend.
 * La URL del backend se deriva del host desde el que se sirve la app
 * (mismo hostname, puerto 8000). Así funciona igual en localhost, por IP de
 * la VM, o detrás de un dominio en producción — sin tocar código.
 *
 * Para apuntar a un backend en OTRO host, fija window.__API_BASE__ antes de
 * cargar la app, o cambia el fallback de abajo.
 */
export default class Config {
	static get API_BASE(): string {
		const override = (window as any).__API_BASE__;
		if (override) { return override as string; }
		const { protocol, hostname } = window.location;
		return `${protocol}//${hostname}:8000`;
	}

	static get WS_BASE(): string {
		return Config.API_BASE.replace(/^http/, "ws");
	}

	static readonly TOKEN_KEY = "ticketdist_token";
	static readonly USER_KEY = "ticketdist_user";
}
