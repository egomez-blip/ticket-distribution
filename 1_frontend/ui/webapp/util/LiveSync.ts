import Config from "./Config";
import Api from "./Api";

type EventHandler = (event: { type: string; [key: string]: unknown }) => void;

/**
 * Cliente WebSocket para sincronización en vivo. Se conecta a
 * /ws?session=<id>&token=<jwt> y despacha cada evento recibido al handler.
 * Reconecta automáticamente si la conexión se cae.
 */
export default class LiveSync {
	private ws: WebSocket | null = null;
	private sessionId: number;
	private handler: EventHandler;
	private closed = false;
	private reconnectTimer: number | null = null;

	constructor(sessionId: number, handler: EventHandler) {
		this.sessionId = sessionId;
		this.handler = handler;
	}

	connect(): void {
		const token = Api.getToken();
		if (!token) { return; }
		const url = `${Config.WS_BASE}/ws?session=${this.sessionId}&token=${encodeURIComponent(token)}`;
		this.ws = new WebSocket(url);

		this.ws.onmessage = (ev: MessageEvent) => {
			try {
				const data = JSON.parse(ev.data as string);
				this.handler(data);
			} catch (e) { /* ignora mensajes no-JSON */ }
		};

		this.ws.onclose = () => {
			if (!this.closed) { this.scheduleReconnect(); }
		};
		this.ws.onerror = () => { this.ws?.close(); };
	}

	private scheduleReconnect(): void {
		if (this.reconnectTimer) { return; }
		this.reconnectTimer = window.setTimeout(() => {
			this.reconnectTimer = null;
			this.connect();
		}, 3000);
	}

	disconnect(): void {
		this.closed = true;
		if (this.reconnectTimer) { window.clearTimeout(this.reconnectTimer); }
		this.ws?.close();
		this.ws = null;
	}
}
