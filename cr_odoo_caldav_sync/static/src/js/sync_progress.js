/** @odoo-module **/

import { registry } from "@web/core/registry";

export const caldavProgressService = {
    dependencies: ["bus_service", "action"],
    start(env, { bus_service, action }) {
        bus_service.subscribe("caldav_sync_progress", (payload) => {
            const controller = action.currentController;
            if (controller) {
                // If viewing the specific CalDAV account form being synced
                if (controller.props.resModel === "caldav.account" && controller.props.resId === payload.account_id) {
                    action.doAction("soft_reload");
                }
                // If viewing the calendar events, reload to show new events
                else if (controller.props.resModel === "calendar.event") {
                    action.doAction("soft_reload");
                }
                // Reload project task, FSM order, maintenance request views to show partial batch saves
                else if (
                    controller.props.resModel === "project.task" ||
                    controller.props.resModel === "fsm.order" ||
                    controller.props.resModel === "maintenance.request"
                ) {
                    action.doAction("soft_reload");
                }
            }
        });
    }
};

registry.category("services").add("caldav_progress_service", caldavProgressService);
