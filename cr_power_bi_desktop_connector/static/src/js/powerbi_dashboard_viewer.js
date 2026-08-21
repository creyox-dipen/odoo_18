/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { useEffect } from "@odoo/owl";

class PowerBIDashboardController extends FormController {
    setup() {
        super.setup();
        useEffect(() => {
            this._loadPowerBIDashboard();
        });
    }

    async _loadPowerBIDashboard() {
        const record = this.model.root;
        const dashboardRecordId = record.data.dashboard_id?.[0];
        if (!dashboardRecordId) return;

        const statusEl = document.getElementById('powerbi_dashboard_status');
        const containerEl = document.getElementById('powerbi_dashboard_container');

        const showStatus = (msg, isError = false) => {
            if (!statusEl) return;
            statusEl.style.display = 'block';
            statusEl.style.background = isError ? '#f8d7da' : '#fff3cd';
            statusEl.style.border = `1px solid ${isError ? '#f5c6cb' : '#ffc107'}`;
            statusEl.style.padding = '10px';
            statusEl.style.borderRadius = '4px';
            statusEl.style.marginBottom = '10px';
            statusEl.innerHTML = msg;
        };

        if (!containerEl) return;

        containerEl.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:center;
                        height:100%;color:#6c757d;flex-direction:column;gap:12px;">
                <div style="width:40px;height:40px;border:4px solid #dee2e6;
                    border-top-color:#0d6efd;border-radius:50%;
                    animation:spin 0.8s linear infinite;"></div>
                <p style="margin:0;">Loading Power BI Dashboard...</p>
                <style>@keyframes spin{to{transform:rotate(360deg);}}</style>
            </div>`;

        try {
            const result = await this.env.services.orm.call(
                'powerbi.dashboard',
                'get_dashboard_embed_data',
                [[dashboardRecordId]],
            );

            if (!result || result.error) {
                showStatus(
                    `❌ ${result ? result.error : 'No response from server'}
                    ${result && result.web_url
                        ? ` — <a href="${result.web_url}" target="_blank">Open in Power BI</a>`
                        : ''}`,
                    true
                );
                containerEl.innerHTML = '';
                return;
            }

            containerEl.innerHTML = '';

            const iframe = document.createElement('iframe');
            iframe.style.width = '100%';
            iframe.style.height = '100%';
            iframe.style.border = 'none';
            iframe.setAttribute('allowfullscreen', 'true');

            iframe.onload = () => {
                const message = {
                    action: 'loadDashboard',
                    accessToken: result.token,
                    width: containerEl.offsetWidth,
                    height: containerEl.offsetHeight,
                };
                iframe.contentWindow.postMessage(JSON.stringify(message), 'https://app.powerbi.com');
                console.log('Token posted to Power BI iframe');
            };

            iframe.src = result.embed_url;
            containerEl.appendChild(iframe);

        } catch (err) {
            console.error('PowerBI dashboard load error:', err);
            showStatus(`❌ Failed: ${err.message || err}`, true);
            containerEl.innerHTML = '';
        }
    }
}

registry.category("views").add("powerbi_dashboard_viewer", {
    ...formView,
    Controller: PowerBIDashboardController,
});