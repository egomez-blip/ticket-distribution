import BaseController from "./BaseController";
import formatter from "../model/formatter";
import Api, { ApiError } from "../util/Api";
import LiveSync from "../util/LiveSync";
import Config from "../util/Config";
import JSONModel from "sap/ui/model/json/JSONModel";
import MessageToast from "sap/m/MessageToast";
import MessageBox from "sap/m/MessageBox";
import BusyIndicator from "sap/ui/core/BusyIndicator";
import Dialog from "sap/m/Dialog";
import Button from "sap/m/Button";
import Select from "sap/m/Select";
import Item from "sap/ui/core/Item";
import Label from "sap/m/Label";
import VBox from "sap/m/VBox";
import Text from "sap/m/Text";
import Table from "sap/m/Table";
import Column from "sap/m/Column";
import ColumnListItem from "sap/m/ColumnListItem";
import Input from "sap/m/Input";

/**
 * Controlador principal: distribución, equipo, skills y correo, sincronizado
 * en vivo con el backend por WebSocket.
 * @namespace com.support.ticketdist.controller
 */
export default class Main extends BaseController {
	public formatter = formatter;
	private live: LiveSync | null = null;

	public onInit(): void {
		this.setModel(new JSONModel({
			sessions: [],
			currentSessionId: null,
			stats: { total: 0, assigned: 0, unassigned: 0, lastNew: 0 },
			team: [],
			allAssignments: [],
			tableRows: [],
			batchItems: [{ key: "all", text: "Todas las cargas" }],
			batchFilter: "all",
			rowFilter: "all",
			activeDim: "ticketType",
			skill: { dimensions: { ticketType: [], systemRole: [], serviceArea: [] }, matrix: {} },
			newMember: { name: "", email: "", cap: 100 },
			email: {
				to_addr: "", cc_addr: "",
				subject: "Distribución de Tickets — {{fecha}}", template: "",
				previewBatch: "last",
				previewItems: [{ key: "last", text: "Última carga" }],
				preview: "Carga un Excel para ver la vista previa."
			}
		}), "v");

		const user = Api.getUser();
		if (user) { this.getAppModel().setProperty("/user", user); }

		this.getRouter().getRoute("main").attachPatternMatched(this._onShow, this);
	}

	private _onShow(): void {
		if (!Api.getToken()) { this.navTo("login", {}, true); return; }
		void this._bootstrap();
	}

	// ─── BOOTSTRAP ──────────────────────────────────────────────
	private async _bootstrap(): Promise<void> {
		BusyIndicator.show(0);
		try {
			await this._loadSessions();
			let sid = this._model().getProperty("/currentSessionId");
			if (!sid) {
				const s = await Api.post("/sessions", {}) as { id: number };
				sid = s.id;
				await this._loadSessions();
				this._model().setProperty("/currentSessionId", String(sid));
			}
			this.getAppModel().setProperty("/sessionId", sid);
			await Promise.all([this._loadTeam(), this._loadSkillMatrix(), this._loadEmailConfig()]);
			await this._refreshSessionData();
			this._connectLive(Number(sid));
		} catch (e) {
			this._err(e);
		} finally {
			BusyIndicator.hide();
		}
	}

	private _model(): JSONModel { return this.getModel("v") as JSONModel; }

	// ─── SESSIONS ───────────────────────────────────────────────
	private async _loadSessions(): Promise<void> {
		const sessions = await Api.get("/sessions") as any[];
		this._model().setProperty("/sessions", sessions.map((s) => ({ ...s, id: String(s.id) })));
		const cur = this._model().getProperty("/currentSessionId");
		if (!cur && sessions.length) {
			this._model().setProperty("/currentSessionId", String(sessions[0].id));
		}
	}

	public async onSessionChange(): Promise<void> {
		const sid = Number(this._model().getProperty("/currentSessionId"));
		this.getAppModel().setProperty("/sessionId", sid);
		this._model().setProperty("/batchFilter", "all");
		await this._refreshSessionData();
		this._connectLive(sid);
	}

	public async onNewSession(): Promise<void> {
		try {
			const s = await Api.post("/sessions", {}) as { id: number };
			await this._loadSessions();
			this._model().setProperty("/currentSessionId", String(s.id));
			await this.onSessionChange();
			MessageToast.show("Nueva sesión creada");
		} catch (e) { this._err(e); }
	}

	// ─── LIVE SYNC ──────────────────────────────────────────────
	private _connectLive(sessionId: number): void {
		if (this.live) { this.live.disconnect(); }
		this.live = new LiveSync(sessionId, (ev) => void this._onLiveEvent(ev));
		this.live.connect();
	}

	private async _onLiveEvent(ev: { type: string; [k: string]: unknown }): Promise<void> {
		switch (ev.type) {
			case "team_changed": await this._loadTeam(); await this._loadSkillMatrix(); break;
			case "skills_changed": await this._loadSkillMatrix(); break;
			case "email_config_changed": await this._loadEmailConfig(); break;
			case "batch_loaded":
			case "assignment_changed":
				if (Number(ev.session_id) === Number(this._model().getProperty("/currentSessionId"))) {
					await this._refreshSessionData();
				}
				break;
			case "session_created": await this._loadSessions(); break;
		}
	}

	// ─── FILE UPLOAD ────────────────────────────────────────────
	public async onFileChange(oEvent: any): Promise<void> {
		const files: FileList = oEvent.getParameter("files");
		const file = files && files[0];
		oEvent.getSource().clear();
		if (!file) { return; }
		const sid = this._model().getProperty("/currentSessionId");
		BusyIndicator.show(0);
		try {
			const res = await Api.upload(`/sessions/${sid}/loads`, file) as { batch_num: number; new_count: number };
			await this._refreshSessionData();
			MessageToast.show(`Carga #${res.batch_num}: ${res.new_count} tickets nuevos asignados`);
		} catch (e) {
			if (e instanceof ApiError && e.status === 409) {
				MessageBox.information(e.message);
			} else { this._err(e); }
		} finally {
			BusyIndicator.hide();
		}
	}

	// ─── REFRESH SESSION DATA ───────────────────────────────────
	private async _refreshSessionData(): Promise<void> {
		const sid = this._model().getProperty("/currentSessionId");
		if (!sid) { return; }
		const [assignments, batches] = await Promise.all([
			Api.get(`/sessions/${sid}/assignments`) as Promise<any[]>,
			Api.get(`/sessions/${sid}/batches`) as Promise<any[]>
		]);
		const m = this._model();
		m.setProperty("/allAssignments", assignments);

		// stats
		const assigned = assignments.filter((a) => a.assignee_id).length;
		const lastNew = batches.length ? batches[batches.length - 1].new_count : 0;
		m.setProperty("/stats", {
			total: assignments.length, assigned, unassigned: assignments.length - assigned, lastNew
		});

		// batch selectors
		m.setProperty("/batchItems", [{ key: "all", text: "Todas las cargas" }].concat(
			batches.map((b) => ({ key: String(b.num), text: `Carga #${b.num} — ${b.new_count} tickets (${b.filename})` }))
		));
		m.setProperty("/email/previewItems", [{ key: "last", text: "Última carga" }]
			.concat(batches.map((b) => ({ key: String(b.num), text: `Carga #${b.num} — ${b.new_count} tickets` })))
			.concat([{ key: "all", text: "Sesión completa" }]));

		this._rebuildTable();
		void this._renderPreview();
	}

	private _rebuildTable(): void {
		const m = this._model();
		const all: any[] = m.getProperty("/allAssignments") || [];
		const bf = m.getProperty("/batchFilter");
		const rf = m.getProperty("/rowFilter");
		let list = all;
		if (bf !== "all") { list = list.filter((a) => String(a.batch_num) === String(bf)); }
		if (rf === "unassigned") { list = list.filter((a) => !a.assignee_id); }

		m.setProperty("/tableRows", list.map((a) => ({
			assignmentId: a.id,
			ticketId: a.ticket.ticket_id,
			batchNum: a.batch_num,
			ticketType: a.ticket.ticket_type || "—",
			priority: a.ticket.priority || "—",
			customerName: a.ticket.customer_name || "—",
			subject: a.ticket.subject || "—",
			systemRole: a.ticket.system_role || "—",
			serviceArea: a.ticket.service_area || "—",
			assigneeId: a.assignee_id,
			assigneeName: a.assignee_id ? a.assignee_name : "Sin asignar",
			isAssigned: !!a.assignee_id,
			overloaded: !!a.overloaded,
			score: a.score,
			altText: (!a.assignee_id && a.alternatives && a.alternatives.length)
				? "Sugeridos: " + a.alternatives.map((x: any) => x.name).join(", ") : ""
		})));
	}

	public onBatchFilterChange(): void { this._rebuildTable(); }
	public onFilterAll(): void { this._model().setProperty("/rowFilter", "all"); this._rebuildTable(); }
	public onFilterUnassigned(): void { this._model().setProperty("/rowFilter", "unassigned"); this._rebuildTable(); }
	public onGoEmail(): void { void this._renderPreview(); (this.byId("itb") as any).setSelectedKey("email"); }

	// ─── TEAM ───────────────────────────────────────────────────
	private async _loadTeam(): Promise<void> {
		this._model().setProperty("/team", await Api.get("/team"));
	}

	public async onAddMember(): Promise<void> {
		const nm = this._model().getProperty("/newMember");
		if (!nm.name || !nm.name.trim()) { MessageToast.show("Ingresa un nombre"); return; }
		try {
			await Api.post("/team", { name: nm.name, email: nm.email, base_cap: Number(nm.cap) || 100 });
			this._model().setProperty("/newMember", { name: "", email: "", cap: 100 });
			await this._loadTeam();
			await this._loadSkillMatrix();
		} catch (e) { this._err(e); }
	}

	public onRemoveMember(oEvent: any): void {
		const ctx = oEvent.getSource().getBindingContext("v");
		const id = ctx.getProperty("id");
		const name = ctx.getProperty("name");
		MessageBox.confirm(`¿Eliminar a ${name} del equipo?`, {
			onClose: async (act: string) => {
				if (act !== MessageBox.Action.OK) { return; }
				try {
					await Api.del(`/team/${id}`);
					await this._loadTeam();
					await this._loadSkillMatrix();
				} catch (e) { this._err(e); }
			}
		});
	}

	public async onToggleActive(oEvent: any): Promise<void> {
		const ctx = oEvent.getSource().getBindingContext("v");
		const id = ctx.getProperty("id");
		const state = oEvent.getParameter("state");
		try { await Api.patch(`/team/${id}`, { active: state }); }
		catch (e) { this._err(e); }
	}

	public async onCapChange(oEvent: any): Promise<void> {
		const ctx = oEvent.getSource().getBindingContext("v");
		const id = ctx.getProperty("id");
		const value = Math.round(oEvent.getParameter("value"));
		try { await Api.patch(`/team/${id}`, { daily_cap: value }); }
		catch (e) { this._err(e); }
	}

	public async onResetCapacities(): Promise<void> {
		try { await Api.post("/team/reset-capacities"); await this._loadTeam(); }
		catch (e) { this._err(e); }
	}

	// ─── SKILLS ─────────────────────────────────────────────────
	private async _loadSkillMatrix(): Promise<void> {
		const data = await Api.get("/skills");
		this._model().setProperty("/skill", data);
		this._buildSkillMatrix();
	}

	public onDimSelect(): void { this._buildSkillMatrix(); }

	private _buildSkillMatrix(): void {
		const box = this.byId("skillBox") as VBox;
		if (!box) { return; }
		box.destroyItems();
		const m = this._model();
		const dim = m.getProperty("/activeDim");
		const cats: string[] = (m.getProperty("/skill/dimensions") || {})[dim] || [];
		const team: any[] = m.getProperty("/team") || [];
		const matrix = m.getProperty("/skill/matrix") || {};

		if (!team.length) { box.addItem(new Text({ text: "Añade colegas en la pestaña Equipo." })); return; }
		if (!cats.length) { box.addItem(new Text({ text: "Carga un Excel para que aparezcan las categorías." })); return; }

		const tbl = new Table({ fixedLayout: false });
		tbl.addColumn(new Column({ width: "160px", header: new Label({ text: "Colega", design: "Bold" }) }));
		cats.forEach((c) => {
			const short = c.length > 16 ? c.slice(0, 14) + "…" : c;
			tbl.addColumn(new Column({ hAlign: "Center", header: new Label({ text: short, tooltip: c }) }));
		});

		team.forEach((member) => {
			const cells: any[] = [new Text({ text: member.name })];
			const memberSkills = (matrix[member.id] || {})[dim] || {};
			cats.forEach((c) => {
				const val = memberSkills[c] || 0;
				cells.push(new Input({
					value: String(val), type: "Number", textAlign: "Center", width: "58px",
					tooltip: `${member.name} — ${c}`,
					change: (ev: any) => {
						const v = Math.min(5, Math.max(0, parseInt(ev.getParameter("value"), 10) || 0));
						ev.getSource().setValue(String(v));
						void this._setSkill(member.id, dim, c, v);
					}
				}));
			});
			tbl.addItem(new ColumnListItem({ cells }));
		});
		box.addItem(tbl);
	}

	private async _setSkill(memberId: number, dimension: string, category: string, level: number): Promise<void> {
		try {
			await Api.put("/skills", { member_id: memberId, dimension, category, level });
			// actualiza el modelo local sin recargar todo
			this._model().setProperty(`/skill/matrix/${memberId}/${dimension}/${category}`, level);
		} catch (e) { this._err(e); }
	}

	// ─── REASSIGN ───────────────────────────────────────────────
	public onReassign(oEvent: any): void {
		const row = oEvent.getSource().getBindingContext("v").getObject();
		const team: any[] = this._model().getProperty("/team");
		const matrix = this._model().getProperty("/skill/matrix") || {};

		const sel = new Select({ width: "100%" });
		sel.addItem(new Item({ key: "", text: "— Sin asignar —" }));
		team.forEach((mMember) => {
			const ms = matrix[mMember.id] || {};
			const avg = ((this._lvl(ms, "ticketType", row.ticketType) +
				this._lvl(ms, "systemRole", row.systemRole) +
				this._lvl(ms, "serviceArea", row.serviceArea)) / 3).toFixed(1);
			sel.addItem(new Item({
				key: String(mMember.id),
				text: `${mMember.name} — Skill: ${avg}/5 | Carga: ${mMember.assigned_today}${mMember.active ? "" : " (ausente)"}`,
				enabled: mMember.active
			}));
		});
		sel.setSelectedKey(row.assigneeId ? String(row.assigneeId) : "");

		const dialog = new Dialog({
			title: `Reasignar: ${row.ticketId}`,
			contentWidth: "460px",
			content: [new VBox({
				items: [
					new Text({ text: `${row.ticketType} | ${row.systemRole} | ${row.serviceArea}` }).addStyleClass("sapUiTinyMarginBottom"),
					new Label({ text: "Asignar a", labelFor: sel }),
					sel
				]
			}).addStyleClass("sapUiContentPadding")],
			beginButton: new Button({
				text: "Confirmar", type: "Emphasized",
				press: async () => {
					const v = sel.getSelectedKey();
					try {
						await Api.patch(`/assignments/${row.assignmentId}`, { assignee_member_id: v ? Number(v) : null });
						await this._refreshSessionData();
						dialog.close();
					} catch (e) { this._err(e); }
				}
			}),
			endButton: new Button({ text: "Cancelar", press: () => dialog.close() }),
			afterClose: () => dialog.destroy()
		});
		this.getView().addDependent(dialog);
		dialog.open();
	}

	private _lvl(ms: any, dim: string, cat: string): number {
		if (!cat || cat === "—") { return 0; }
		return (ms[dim] || {})[cat] || 0;
	}

	// ─── EMAIL ──────────────────────────────────────────────────
	private async _loadEmailConfig(): Promise<void> {
		const cfg = await Api.get("/email/config");
		const email = this._model().getProperty("/email");
		this._model().setProperty("/email", { ...email, ...cfg });
	}

	public async onEmailFieldChange(): Promise<void> {
		const e = this._model().getProperty("/email");
		try {
			await Api.put("/email/config", {
				to_addr: e.to_addr, cc_addr: e.cc_addr, subject: e.subject, template: e.template
			});
			void this._renderPreview();
		} catch (err) { this._err(err); }
	}

	public onPreviewBatchChange(): void { void this._renderPreview(); }

	private async _renderPreview(): Promise<void> {
		const sid = this._model().getProperty("/currentSessionId");
		if (!sid) { return; }
		const batch = this._model().getProperty("/email/previewBatch");
		try {
			const res = await Api.get(`/email/preview/${sid}?batch=${batch}`) as { body: string };
			this._model().setProperty("/email/preview", res.body);
		} catch (e) { /* silencioso en preview */ }
	}

	public onCopyBody(): void {
		const body = this._model().getProperty("/email/preview");
		void navigator.clipboard.writeText(body).then(() => MessageToast.show("Cuerpo copiado al portapapeles"));
	}

	public onOpenOutlook(): void {
		const e = this._model().getProperty("/email");
		const subject = (e.subject || "").replace(/\{\{fecha\}\}/g, new Date().toLocaleDateString("es-ES"));
		const to = encodeURIComponent(e.to_addr || "");
		const cc = encodeURIComponent(e.cc_addr || "");
		const sub = encodeURIComponent(subject);
		const body = e.preview || "";
		void navigator.clipboard.writeText(body);
		const link = `mailto:${to}?cc=${cc}&subject=${sub}&body=${encodeURIComponent(body)}`;
		if (link.length > 2000) {
			window.location.href = `mailto:${to}?cc=${cc}&subject=${sub}`;
			setTimeout(() => MessageBox.information("El email es largo — el cuerpo fue copiado al portapapeles. Pégalo en Outlook con Ctrl+V."), 400);
		} else {
			window.location.href = link;
		}
	}

	// ─── LOGOUT / ERRORS ────────────────────────────────────────
	public onLogout(): void {
		if (this.live) { this.live.disconnect(); }
		Api.clear();
		this.navTo("login", {}, true);
	}

	private _err(e: unknown): void {
		if (e instanceof ApiError && e.status === 401) {
			this.onLogout();
			return;
		}
		const msg = e instanceof ApiError ? e.message : "Error de conexión con el servidor";
		MessageToast.show(msg);
	}
}
