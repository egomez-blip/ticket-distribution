import Controller from "sap/ui/core/mvc/Controller";
import UIComponent from "sap/ui/core/UIComponent";
import Router from "sap/ui/core/routing/Router";
import Model from "sap/ui/model/Model";
import JSONModel from "sap/ui/model/json/JSONModel";

/**
 * @namespace com.support.ticketdist.controller
 */
export default abstract class BaseController extends Controller {
	public getRouter(): Router {
		return UIComponent.getRouterFor(this);
	}

	public getModel(name?: string): Model {
		return this.getView().getModel(name);
	}

	public setModel(model: Model, name?: string): void {
		this.getView().setModel(model, name);
	}

	/** Modelo global "app" (usuario, sesión activa) definido en Component. */
	public getAppModel(): JSONModel {
		return this.getOwnerComponent().getModel("app") as JSONModel;
	}

	public navTo(name: string, params?: object, replace?: boolean): void {
		this.getRouter().navTo(name, params, undefined, replace);
	}
}
