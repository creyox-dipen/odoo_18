/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, useState } = owl;

export class BiometricDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            darkMode: localStorage.getItem('biometric_dark_mode') !== 'false',
            data: {
                total_employees: 0,
                present_count: 0,
                absent_count: 0,
                leave_count: 0,
                late_count: 0,
                early_count: 0,
                device_stats: [],
                recent_punches: [],
                presented_employees: [],
                absented_employees: [],
                leaved_employees: [],
            }
        });

        onWillStart(async () => {
            await this.fetchData();
        });
    }

    toggleTheme() {
        this.state.darkMode = !this.state.darkMode;
        localStorage.setItem('biometric_dark_mode', this.state.darkMode);
    }

    async fetchData() {
        const result = await this.orm.call("biometric.dashboard", "get_dashboard_data", []);
        if (result) {
            this.state.data = result;
        }
    }

    async refreshData() {
        await this.fetchData();
    }

    viewAllLogs() {
        this.action.doAction("cr_zkteco_biometric_integration.action_biometric_attendance_log");
    }

    openEmployee(empId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.employee',
            res_id: empId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    openDevice(deviceId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'biometric.device',
            res_id: deviceId,
            views: [[false, 'form']],
            target: 'current',
        });
    }
}

BiometricDashboard.template = "cr_zkteco_biometric_integration.BiometricDashboard";

registry.category("actions").add("biometric_dashboard_action", BiometricDashboard);
