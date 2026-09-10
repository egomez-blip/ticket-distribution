import UIComponent from "sap/ui/core/UIComponent";
import JSONModel from "sap/ui/model/json/JSONModel";

/**
 * @namespace com.support.ticketdist
 */
export default class Component extends UIComponent {
	public static metadata = {
		manifest: "json",
		interfaces: ["sap.ui.core.IAsyncContentCreation"]
	};

	public init(): void {
		super.init();

		// Modelo global de sesión (usuario, sesión de trabajo activa)
		this.setModel(new JSONModel({
			user: null,
			sessionId: null,
			sessionName: null
		}), "app");

		this.getRouter().initialize();
	}
}
