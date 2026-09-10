import BaseController from "./BaseController";
import Api, { ApiError } from "../util/Api";
import Input from "sap/m/Input";
import MessageToast from "sap/m/MessageToast";
import BusyIndicator from "sap/ui/core/BusyIndicator";

/**
 * @namespace com.support.ticketdist.controller
 */
export default class Login extends BaseController {
	public async onLogin(): Promise<void> {
		const email = (this.byId("emailInput") as Input).getValue().trim();
		const password = (this.byId("passwordInput") as Input).getValue();
		if (!email || !password) {
			MessageToast.show("Ingresa email y contraseña");
			return;
		}
		BusyIndicator.show(0);
		try {
			const data = await Api.post("/auth/login", { email, password }) as {
				access_token: string; user: object;
			};
			Api.setSession(data.access_token, data.user);
			this.getAppModel().setProperty("/user", data.user);
			this.navTo("main", {}, true);
		} catch (e) {
			const msg = e instanceof ApiError ? e.message : "Error de conexión con el servidor";
			MessageToast.show(msg);
		} finally {
			BusyIndicator.hide();
		}
	}
}
