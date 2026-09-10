import BaseController from "./BaseController";
import Api from "../util/Api";

/**
 * Shell de la app: guard de autenticación en cada cambio de ruta.
 * @namespace com.support.ticketdist.controller
 */
export default class App extends BaseController {
	public onInit(): void {
		this.getRouter().attachRouteMatched(this._onRouteMatched, this);
	}

	private _onRouteMatched(oEvent: any): void {
		const routeName = oEvent.getParameter("name") as string;
		const hasToken = !!Api.getToken();

		if (routeName !== "login" && !hasToken) {
			// Sin token: fuera del login → volver al login
			this.navTo("login", {}, true);
		} else if (routeName === "login" && hasToken) {
			// Ya autenticado y en login → ir a la app
			this.navTo("main", {}, true);
		}
	}
}
