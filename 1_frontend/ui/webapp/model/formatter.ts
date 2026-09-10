/**
 * Funciones de formato puras usadas en las vistas.
 * @namespace com.support.ticketdist.model
 */
const formatter = {
	/** Prioridad → ValueState (color) para ObjectStatus. */
	priorityState(p: string): string {
		if (!p) { return "None"; }
		const lp = p.toLowerCase();
		if (/\b1\b|critical|very high|high/.test(lp)) { return "Error"; }
		if (/\b4\b|low/.test(lp)) { return "Success"; }
		return "Warning";
	},

	/** score (0-5) → porcentaje entero. */
	scorePct(score: number): number {
		return Math.round(((score || 0) / 5) * 100);
	},

	/** Estado del asignado: verde si asignado, rojo si no. */
	assigneeState(isAssigned: boolean): string {
		return isAssigned ? "Success" : "Error";
	},

	/** Iniciales para el avatar. */
	initials(name: string): string {
		if (!name) { return "?"; }
		return name.split(" ").map((x) => x[0]).slice(0, 2).join("").toUpperCase();
	}
};

export default formatter;
