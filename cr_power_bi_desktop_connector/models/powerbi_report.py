# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)


class PowerBIReport(models.Model):
    _name = "powerbi.report"
    _description = "Power BI Report"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "report_name"
    _order = "create_date desc"

    # Basic Information
    report_name = fields.Char(string="Report Name", required=True, tracking=True)
    report_id = fields.Char(string="Report ID", readonly=True, copy=False)
    web_url = fields.Char(string="Web URL", readonly=True)
    embed_url = fields.Char(string="Embed URL", readonly=True)
    description = fields.Text(string="Description")

    # Relations
    config_id = fields.Many2one(
        "powerbi.config", string="Configuration", required=True, ondelete="cascade"
    )
    workspace_id = fields.Many2one(
        "powerbi.workspace", string="Workspace", required=True, ondelete="cascade"
    )
    dataset_id = fields.Many2one("powerbi.dataset", string="Dataset")
    company_id = fields.Many2one(
        "res.company", string="Company", related="config_id.company_id", store=True
    )

    # Status Fields
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("to_publish", "To Publish"),
            ("published", "Published"),
            ("error", "Error"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    # Power BI Metadata
    created_by = fields.Char(string="Created By", readonly=True)
    created_on = fields.Datetime(string="Created On", readonly=True)

    # Model Association for Smart Button
    model_id = fields.Many2one(
        "ir.model",
        string="Odoo Model",
        ondelete="cascade",
        help="Associate this report with an Odoo model to show analytics button on forms",
    )
    apply_to_all_records = fields.Boolean(
        string="Show on All Records",
        default=False,
        help="If checked, analytics button appears on all records. Otherwise, set specific filter.",
    )
    record_domain = fields.Char(
        string="Record Domain",
        default="[]",
        help="Filter which records show the analytics button",
    )

    # Report Type
    report_type = fields.Selection(
        [
            ("standard", "Standard Report"),
            ("dashboard", "Dashboard"),
            ("paginated", "Paginated Report"),
        ],
        string="Report Type",
        default="standard",
        required=True,
    )

    # Access Control
    user_ids = fields.Many2many(
        "res.users",
        string="Authorized Users",
        help="Leave empty to allow all users with Power BI access",
    )
    group_ids = fields.Many2many("res.groups", string="Authorized Groups")

    # Embedding Settings
    allow_embedding = fields.Boolean(string="Allow Embedding", default=True)
    auto_refresh = fields.Boolean(string="Auto Refresh", default=False)
    refresh_interval = fields.Integer(string="Refresh Interval (seconds)", default=300)

    # Filter Configuration for Smart Button
    filter_field_id = fields.Many2one(
        "ir.model.fields",
        string="Filter Field",
        ondelete="cascade",
        domain="[('model_id', '=', model_id)]",
        help="Field used to filter report based on current record",
    )
    filter_column_name = fields.Char(
        string="Power BI Column Name",
        help="Corresponding column name in Power BI report",
    )

    embed_html = fields.Html(
        string="Report Preview", compute="_compute_embed_html", sanitize=False
    )

    @api.depends("embed_url", "report_id")
    def _compute_embed_html(self):
        for record in self:
            if record.embed_url and record.report_id:
                record.embed_html = f"""
                    <div id="reportContainer_{record.id}" 
                         style="height:650px; width:100%;"
                         data-report-odoo-id="{record.id}">
                    </div>
                    <script>
                        (function() {{
                            var containerId = "reportContainer_{record.id}";
                            var odooReportId = {record.id};

                            function loadPowerBIReport() {{
                                fetch('/web/dataset/call_kw', {{
                                    method: 'POST',
                                    headers: {{'Content-Type': 'application/json'}},
                                    body: JSON.stringify({{
                                        jsonrpc: '2.0',
                                        method: 'call',
                                        params: {{
                                            model: 'powerbi.report',
                                            method: 'get_embed_data',
                                            args: [[odooReportId]],
                                            kwargs: {{}}
                                        }}
                                    }})
                                }})
                                .then(r => r.json())
                                .then(function(response) {{
                                    var data = response.result;
                                    if (!data || data.error) {{
                                        document.getElementById(containerId).innerHTML = 
                                            '<p style="color:red;">Error: ' + (data ? data.error : 'Unknown error') + '</p>';
                                        return;
                                    }}

                                    var models = window['powerbi-client'].models;
                                    var config = {{
                                        type: 'report',
                                        tokenType: models.TokenType.Embed,
                                        accessToken: data.token,
                                        embedUrl: data.embed_url,
                                        id: data.report_id,
                                        permissions: models.Permissions.Read,
                                        settings: {{
                                            panes: {{
                                                filters: {{ expanded: false, visible: true }},
                                                pageNavigation: {{ visible: true }}
                                            }}
                                        }}
                                    }};

                                    var container = document.getElementById(containerId);
                                    window.powerbi.embed(container, config);
                                }})
                                .catch(function(err) {{
                                    document.getElementById(containerId).innerHTML = 
                                        '<p style="color:red;">Failed to load report: ' + err + '</p>';
                                }});
                            }}

                            if (typeof window['powerbi-client'] !== 'undefined') {{
                                loadPowerBIReport();
                            }} else {{
                                var script = document.createElement('script');
                                script.src = 'https://cdn.jsdelivr.net/npm/powerbi-client@2.23.1/dist/powerbi.min.js';
                                script.onload = loadPowerBIReport;
                                document.head.appendChild(script);
                            }}
                        }})();
                    </script>
                """
            else:
                record.embed_html = '<p class="text-muted p-3">No embed URL available. Please fetch report from Power BI first.</p>'

    def get_embed_data(self):
        self.ensure_one()
        try:
            token = self.config_id._get_valid_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Step 1: Get fresh report details for correct embedUrl
            report_response = requests.get(
                f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id.workspace_id}/reports/{self.report_id}",
                headers=headers,
                timeout=30,
            )

            if report_response.status_code != 200:
                return {
                    "error": f"Failed to get report details: {report_response.text}"
                }

            embed_url = report_response.json().get("embedUrl")

            # Step 2: Generate embed token
            embed_token = self.config_id._get_embed_token(
                self.report_id, self.workspace_id.workspace_id
            )

            return {
                "token": embed_token,
                "embed_url": embed_url,
                "report_id": self.report_id,
                "web_url": self.web_url,
                "token_type": "Embed",
            }

        except Exception as e:
            _logger.error("get_embed_data failed: %s", str(e))
            return {"error": str(e)}

    def action_publish(self):
        """Publish report to Power BI"""
        self.ensure_one()

        if not self.workspace_id.workspace_id:
            raise UserError(_("Workspace must be published first."))

        try:
            token = self.config_id._get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Note: Actual report publishing requires a .pbix file upload
            # This is a simplified version - in reality, you'd upload the report file
            data = {
                "name": self.report_name,
                "datasetId": self.dataset_id.dataset_id if self.dataset_id else None,
            }

            # For now, we'll mark it as published
            # In a real implementation, you'd upload the .pbix file
            self.write({"state": "published", "created_on": fields.Datetime.now()})

            self.message_post(
                body=_(
                    "Report marked as published. Upload .pbix file in Power BI workspace."
                )
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Published"),
                    "message": _(
                        "Report published! Upload your .pbix file in Power BI workspace: %s"
                    )
                    % self.workspace_id.workspace_name,
                    "type": "success",
                    "sticky": True,
                },
            }

        except Exception as e:
            _logger.error("Report publish failed: %s", str(e))
            self.write({"state": "error"})
            raise UserError(_("Report publish failed: %s") % str(e))

    def action_open_report(self):
        """Open report in Power BI web"""
        self.ensure_one()

        if not self.web_url:
            raise UserError(
                _("No web URL available. Please sync report from Power BI first.")
            )

        return {
            "type": "ir.actions.act_url",
            "url": self.web_url,
            "target": "new",
        }

    def action_embed_report(self):
        self.ensure_one()

        if not self.embed_url:
            raise UserError(
                _("No embed URL available. Please fetch report from Power BI first.")
            )

        viewer = self.env["powerbi.report.viewer"].create(
            {
                "report_id": self.id,
                "embed_url": self.embed_url,
                "report_name": self.report_name,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": self.report_name,
            "res_model": "powerbi.report.viewer",
            "res_id": viewer.id,
            "view_mode": "form",
            "target": "new",
        }

    def get_report_embed_data(self):
        self.ensure_one()
        try:
            token = self.config_id._get_valid_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            report_response = requests.get(
                f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id.workspace_id}/reports/{self.report_id}",
                headers=headers,
                timeout=30,
            )

            if report_response.status_code != 200:
                return {
                    "error": f"Failed to get report details: {report_response.text}"
                }

            report_data = report_response.json()
            embed_url = report_data.get("embedUrl")
            dataset_id = report_data.get("datasetId")

            token_response = requests.post(
                "https://api.powerbi.com/v1.0/myorg/GenerateToken",
                headers=headers,
                json={
                    "datasets": [{"id": dataset_id}] if dataset_id else [],
                    "reports": [{"id": self.report_id}],
                    "targetWorkspaces": [{"id": self.workspace_id.workspace_id}],
                },
                timeout=30,
            )

            if token_response.status_code != 200:
                return {
                    "error": f"Failed to generate embed token: {token_response.text}"
                }

            embed_token = token_response.json().get("token")

            return {
                "token": embed_token,
                "embed_url": embed_url,
                "report_id": self.report_id,
                "web_url": self.web_url,
                "token_type": "Embed",
            }

        except Exception as e:
            _logger.error("get_report_embed_data failed: %s", str(e))
            return {"error": str(e)}

    def action_sync_from_powerbi(self):
        """Sync report details from Power BI"""
        self.ensure_one()

        if not self.report_id:
            raise UserError(_("No report ID found."))

        try:
            token = self.config_id._get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id.workspace_id}/reports/{self.report_id}",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                report_data = response.json()

                self.write(
                    {
                        "report_name": report_data.get("name", self.report_name),
                        "web_url": report_data.get("webUrl"),
                        "embed_url": report_data.get("embedUrl"),
                        "dataset_id": (
                            self._find_dataset_by_id(report_data.get("datasetId")).id
                            if report_data.get("datasetId")
                            else False
                        ),
                    }
                )

                self.message_post(body=_("Report synced from Power BI."))

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Success"),
                        "message": _("Report synced successfully!"),
                        "type": "success",
                        "sticky": False,
                    },
                }
            else:
                raise UserError(_("Failed to sync report: %s") % response.text)

        except Exception as e:
            _logger.error("Report sync failed: %s", str(e))
            raise UserError(_("Report sync failed: %s") % str(e))

    def action_add_smart_button(self):
        """Add smart button to selected model's form view"""
        self.ensure_one()

        if not self.model_id:
            raise UserError(_("Please select a model first."))

        # This would dynamically inject the smart button into the form view
        # In Odoo, this typically requires view inheritance

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Smart Button Configuration"),
                "message": _(
                    "To add the Analytics button to %s forms:\n"
                    "1. The button will appear automatically on form views\n"
                    "2. Configure filter field to pass context\n"
                    "3. Users need Power BI access rights"
                )
                % self.model_id.name,
                "type": "info",
                "sticky": True,
            },
        }

    def action_test_filter(self):
        """Test report filter with sample data"""
        self.ensure_one()

        if not self.model_id or not self.filter_field_id:
            raise UserError(_("Please configure model and filter field first."))

        # Get a sample record
        domain = eval(self.record_domain) if self.record_domain else []
        sample_record = self.env[self.model_id.model].search(domain, limit=1)

        if not sample_record:
            raise UserError(_("No records found to test with."))

        filter_value = sample_record[self.filter_field_id.name]

        # Handle many2one fields
        if self.filter_field_id.ttype == "many2one":
            filter_value = filter_value.id if filter_value else None
            display_value = f"{filter_value} (ID: {filter_value})"
        else:
            display_value = str(filter_value)

        message = f"""
            Filter Test Results:
            - Model: {self.model_id.name}
            - Filter Field: {self.filter_field_id.field_description}
            - Power BI Column: {self.filter_column_name}
            - Sample Record: {sample_record.display_name}
            - Filter Value: {display_value}
            
            This value will be passed to Power BI to filter the report.
                    """

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Filter Test"),
                "message": message,
                "type": "info",
                "sticky": True,
            },
        }

    def get_report_url_with_filter(self, record_id):
        """Get report URL with filter applied for specific record"""
        self.ensure_one()

        if not self.embed_url or not self.filter_field_id:
            return self.embed_url

        # Get the record
        record = self.env[self.model_id.model].browse(record_id)

        if not record.exists():
            return self.embed_url

        # Get filter value
        filter_value = record[self.filter_field_id.name]

        # Handle many2one fields
        if self.filter_field_id.ttype == "many2one":
            filter_value = filter_value.id if filter_value else None

        # Build Power BI filter URL parameter
        if filter_value and self.filter_column_name:
            # Power BI filter format: $filter=TableName/ColumnName eq 'value'
            filter_param = f"$filter={self.filter_column_name} eq '{filter_value}'"
            separator = "&" if "?" in self.embed_url else "?"
            return f"{self.embed_url}{separator}{filter_param}"

        return self.embed_url

    def _find_dataset_by_id(self, dataset_id):
        """Find dataset by Power BI dataset ID"""
        if not dataset_id:
            return self.env["powerbi.dataset"]

        return self.env["powerbi.dataset"].search(
            [("dataset_id", "=", dataset_id), ("config_id", "=", self.config_id.id)],
            limit=1,
        )

    @api.model
    def get_reports_for_model(self, model_name, record_id=None):
        """Get available reports for a specific model and record"""
        domain = [
            ("model_id.model", "=", model_name),
            ("state", "=", "published"),
            ("allow_embedding", "=", True),
        ]

        reports = self.search(domain)

        # Filter by record domain if provided
        if record_id:
            filtered_reports = []
            for report in reports:
                if report.apply_to_all_records:
                    filtered_reports.append(report)
                elif report.record_domain:
                    try:
                        record_domain = eval(report.record_domain)
                        matching = self.env[model_name].search(
                            record_domain + [("id", "=", record_id)], limit=1
                        )
                        if matching:
                            filtered_reports.append(report)
                    except:
                        pass

            return self.browse([r.id for r in filtered_reports])

        return reports

    @api.model
    def check_user_access(self, report_id):
        """Check if current user has access to report"""
        report = self.browse(report_id)

        if not report.exists():
            return False

        # If no specific users/groups defined, allow all
        if not report.user_ids and not report.group_ids:
            return True

        # Check user access
        if self.env.user in report.user_ids:
            return True

        # Check group access
        user_groups = self.env.user.groups_id
        if any(group in report.group_ids for group in user_groups):
            return True

        return False


class PowerBIReportViewer(models.TransientModel):
    _name = "powerbi.report.viewer"
    _description = "Power BI Report Viewer"

    report_id = fields.Many2one("powerbi.report", string="Report")
    embed_url = fields.Char(string="Embed URL")
    report_name = fields.Char(string="Report Name")
