/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { useEffect } from "@odoo/owl";

class PowerBIFormController extends FormController {
    setup() {
        super.setup();
        useEffect(() => {
            this._loadPowerBIReport();
        });
    }

    async _loadPowerBIReport() {
        const record = this.model.root;
        const reportId = record.data.report_id?.[0];

        if (!reportId) return;

        const statusEl = document.getElementById('powerbi_status');
        const containerEl = document.getElementById('powerbi_report_container');

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

        const hideStatus = () => {
            if (statusEl) statusEl.style.display = 'none';
        };

        const showLoading = () => {
            if (!containerEl) return;
            containerEl.innerHTML = `
                <div style="display:flex; align-items:center; justify-content:center;
                            height:100%; color:#6c757d; flex-direction:column; gap:12px;">
                    <div style="
                        width: 40px; height: 40px;
                        border: 4px solid #dee2e6;
                        border-top-color: #0d6efd;
                        border-radius: 50%;
                        animation: spin 0.8s linear infinite;">
                    </div>
                    <p style="margin:0;">Loading Power BI Report...</p>
                    <style>
                        @keyframes spin { to { transform: rotate(360deg); } }
                    </style>
                </div>
            `;
        };

        try {
            showLoading();

            // Fetch embed token and config from backend
            const result = await this.env.services.orm.call(
                'powerbi.report',
                'get_report_embed_data',
                [[reportId]],
            );

            if (!result || result.error) {
                showStatus(
                    `❌ Error: ${result ? result.error : 'No response from server'}
                    ${result && result.web_url
                        ? ` — <a href="${result.web_url}" target="_blank">Open in Power BI instead</a>`
                        : ''
                    }`,
                    true
                );
                if (containerEl) containerEl.innerHTML = '';
                return;
            }

            // Load Power BI JS SDK from CDN
            await this._loadSDK();

            const pbiModels = window['powerbi-client'].models;

            // Use Embed token type (requires Premium/PPU trial)
            const tokenType = result.token_type === 'Embed'
                ? pbiModels.TokenType.Embed
                : pbiModels.TokenType.Aad;

            const config = {
                type: 'report',
                tokenType: tokenType,
                accessToken: result.token,
                embedUrl: result.embed_url,
                id: result.report_id,
                permissions: pbiModels.Permissions.Read,
                settings: {
                    background: pbiModels.BackgroundType.Transparent,
                    panes: {
                        filters: {
                            expanded: false,
                            visible: true,
                        },
                        pageNavigation: {
                            visible: true,
                            position: pbiModels.PageNavigationPosition.Bottom,
                        },
                    },
                },
            };

            if (containerEl) {
                containerEl.innerHTML = '';

                const report = window.powerbi.embed(containerEl, config);

                report.on('loaded', () => {
                    hideStatus();
                    console.log('Power BI report loaded successfully');
                });

                report.on('rendered', () => {
                    console.log('Power BI report rendered successfully');
                });

                report.on('error', (event) => {
                    const detail = event.detail || {};
                    const msg = detail.message || 'Unknown error';
                    const detailedMsg = detail.detailedMessage || '';
                    const errorCode = detail.errorCode || '';

                    console.error('Power BI embed error:', detail);

                    showStatus(
                        `❌ Embed error: <strong>${msg}</strong>
                        ${detailedMsg ? ' — ' + detailedMsg : ''}
                        (Code: ${errorCode})
                        ${result.web_url
                            ? ` — <a href="${result.web_url}" target="_blank">Open in Power BI instead</a>`
                            : ''
                        }`,
                        true
                    );
                });
            }

        } catch (err) {
            console.error('PowerBI load error:', err);
            showStatus(
                `❌ Failed to load report: ${err.message || err}`,
                true
            );
            if (containerEl) containerEl.innerHTML = '';
        }
    }

    _loadSDK() {
        return new Promise((resolve, reject) => {
            // Already loaded
            if (window['powerbi-client'] && window.powerbi) {
                resolve();
                return;
            }
            // Script tag already injected, wait for it
            const existing = document.querySelector('script[src*="powerbi-client"]');
            if (existing) {
                existing.addEventListener('load', resolve);
                existing.addEventListener('error', () => reject(new Error('Power BI SDK failed to load')));
                return;
            }
            // Inject SDK script
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/powerbi-client@2.23.1/dist/powerbi.min.js';
            script.onload = () => {
                console.log('Power BI SDK loaded from CDN');
                resolve();
            };
            script.onerror = () => {
                reject(new Error('Failed to load Power BI SDK from CDN — check network/CSP settings'));
            };
            document.head.appendChild(script);
        });
    }
}

registry.category("views").add("powerbi_report_viewer", {
    ...formView,
    Controller: PowerBIFormController,
});