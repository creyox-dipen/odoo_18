# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class PowerBIConfig(models.Model):
    _name = "powerbi.config"
    _description = "Power BI Configuration"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"

    # Basic Information
    name = fields.Char(string="Account Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    # Authentication Fields
    client_id = fields.Char(string="Client ID")
    client_secret = fields.Char(string="Client Secret")
    tenant_id = fields.Char(string="Tenant ID")
    access_token = fields.Char(string="Access Token", readonly=True)
    token_expiry = fields.Datetime(string="Token Expiry", readonly=True)
    username = fields.Char(string="Username")
    password = fields.Char(string="Password")

    # User-Based Token Settings
    use_user_token = fields.Boolean(string="Use User-Based Tokens", default=False)

    # Status and Statistics
    state = fields.Selection(
        [("draft", "Draft"), ("connected", "Connected"), ("error", "Error")],
        string="Status",
        default="draft",
        readonly=True,
    )

    last_sync_date = fields.Datetime(string="Last Sync Date", readonly=True)
    connection_test_result = fields.Text(string="Connection Test Result", readonly=True)

    # Counters for Smart Buttons
    workspace_count = fields.Integer(
        string="Workspaces", compute="_compute_counts", store=True
    )
    eventhouse_count = fields.Integer(
        string="Eventhouses", compute="_compute_counts", store=True
    )
    database_count = fields.Integer(
        string="Databases", compute="_compute_counts", store=True
    )

    dataset_count = fields.Integer(
        string="Datasets", compute="_compute_counts", store=True
    )
    report_count = fields.Integer(
        string="Reports", compute="_compute_counts", store=True
    )

    # Notes
    notes = fields.Text(string="Notes")

    @api.depends(
        "workspace_ids",
        "eventhouse_ids",
        "database_ids",
        "dataset_ids",
        "report_ids",
    )
    def _compute_counts(self):
        for record in self:
            record.workspace_count = len(record.workspace_ids)
            record.eventhouse_count = len(record.eventhouse_ids)
            record.database_count = len(record.database_ids)
            record.dataset_count = len(record.dataset_ids)
            record.report_count = len(record.report_ids)

    # One2many Relations
    workspace_ids = fields.One2many(
        "powerbi.workspace", "config_id", string="Workspaces"
    )
    eventhouse_ids = fields.One2many(
        "powerbi.eventhouse", "config_id", string="Eventhouses"
    )
    database_ids = fields.One2many(
        "powerbi.kql.database", "config_id", string="KQL Databases"
    )
    dataset_ids = fields.One2many("powerbi.dataset", "config_id", string="Datasets")
    report_ids = fields.One2many("powerbi.report", "config_id", string="Reports")

    _sql_constraints = [
        (
            "name_company_uniq",
            "unique(name, company_id)",
            "Configuration name must be unique per company!",
        )
    ]

    # Desktop Connector fields — reads/writes the single cr.power.bi.configuration record
    connector_config_id = fields.Many2one(
        "cr.power.bi.configuration",
        string="Connector Config",
        compute="_compute_connector_config",
    )
    cr_connector_url = fields.Char(
        string="Connector URL",
        related="connector_config_id.cr_connector_url",
        readonly=True,
    )
    cr_access_token = fields.Char(
        string="Access Token",
        related="connector_config_id.cr_access_token",
        readonly=True,
    )

    def _compute_connector_config(self):
        config = self.env["cr.power.bi.configuration"].sudo().search([], limit=1)
        if not config:
            config = self.env["cr.power.bi.configuration"].sudo().create({})
        for rec in self:
            rec.connector_config_id = config

    def action_generate_connector_token(self):
        self.ensure_one()
        self.connector_config_id.generate_token()

    def _get_embed_token(self, report_id, workspace_id):
        """Generate Power BI embed token (requires Premium/PPU)"""
        try:
            token = self._get_valid_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/reports/{report_id}/GenerateToken",
                headers=headers,
                json={"accessLevel": "View"},
                timeout=30,
            )

            if response.status_code == 200:
                return response.json().get("token")
            else:
                raise UserError(_("Failed to generate embed token: %s") % response.text)

        except Exception as e:
            _logger.error("_get_embed_token failed: %s", str(e))
            raise

    def action_fetch_pipelines(self):
        """Fetch deployment pipelines from Power BI"""
        self.ensure_one()

        try:
            token = self._get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Fetch pipelines
            response = requests.get(
                "https://api.powerbi.com/v1.0/myorg/pipelines",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                pipelines_data = response.json()
                pipelines_list = pipelines_data.get("value", [])

                synced_count = 0
                error_count = 0

                for pipeline in pipelines_list:
                    try:
                        self._sync_pipeline(pipeline)
                        synced_count += 1
                    except Exception as e:
                        _logger.error(
                            "Failed to sync pipeline %s: %s", pipeline.get("id"), str(e)
                        )
                        error_count += 1

                message = _("%d pipeline(s) synced successfully.") % synced_count
                if error_count > 0:
                    message += _(" %d failed.") % error_count

                self.message_post(body=message)

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Success"),
                        "message": message,
                        "type": "success" if error_count == 0 else "warning",
                        "sticky": False,
                    },
                }

            elif response.status_code == 401:
                raise UserError(
                    _("Authentication failed. Please check your Power BI credentials.")
                )

            elif response.status_code == 403:
                raise UserError(
                    _(
                        "Access denied. Your account may not have permission to view pipelines."
                    )
                )

            else:
                error_msg = f"Failed to fetch pipelines: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                raise UserError(_(error_msg))

        except requests.exceptions.Timeout:
            raise UserError(_("Request timed out. Please try again."))

        except requests.exceptions.ConnectionError:
            raise UserError(
                _(
                    "Could not connect to Power BI. Please check your internet connection."
                )
            )

        except Exception as e:
            _logger.error("Pipeline fetch failed: %s", str(e))
            raise UserError(_("Pipeline fetch failed: %s") % str(e))

    def _sync_pipeline(self, pipeline_data):
        """Sync a single pipeline to Odoo"""

        pipeline_id = pipeline_data.get("id")

        # Check if pipeline already exists
        existing_pipeline = self.env["powerbi.pipeline"].search(
            [("pipeline_id", "=", pipeline_id)], limit=1
        )

        # Get token for API call
        token = self._get_valid_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Fetch pipeline stages from API
        response = requests.get(
            f"https://api.powerbi.com/v1.0/myorg/pipelines/{pipeline_id}/stages",
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            _logger.error(
                "Failed to fetch stages for pipeline %s: %s", pipeline_id, response.text
            )
            stages_data = []
        else:
            stages_response = response.json()
            stages_data = stages_response.get("value", [])

        # Prepare pipeline values
        values = {
            "name": pipeline_data.get("displayName", "Unnamed Pipeline"),
            "pipeline_id": pipeline_id,
            "description": pipeline_data.get("description", ""),
            "config_id": self.id,
        }

        # Create or update pipeline
        if existing_pipeline:
            pipeline = existing_pipeline
            pipeline.write(values)
        else:
            pipeline = self.env["powerbi.pipeline"].create(values)

        # THIS IS WHERE _sync_pipeline_stages GETS CALLED ↓
        self._sync_pipeline_stages(pipeline, stages_data)

        return pipeline

    def _sync_pipeline_stages(self, pipeline, stages_data):
        """Sync pipeline stages from API response"""

        # Define default stage names
        default_stage_names = ["Development", "Test", "Production"]

        # Determine how many stages to create
        stages_count = max(len(stages_data), 3)  # At least 3 stages

        # Get existing stages for this pipeline
        existing_stages = self.env["powerbi.pipeline.stage"].search(
            [("pipeline_id", "=", pipeline.id)]
        )

        # Create a mapping of existing stages by sequence
        existing_by_sequence = {stage.sequence: stage for stage in existing_stages}

        created_count = 0
        updated_count = 0

        for idx in range(stages_count):
            sequence = (idx + 1) * 10  # 10, 20, 30, etc.

            # Determine stage name
            if idx < len(default_stage_names):
                stage_name = default_stage_names[idx]
            else:
                stage_name = f"Stage {idx + 1}"

            # Get workspace_id from API data if available
            powerbi_workspace_id = None
            workspace_record = None

            if idx < len(stages_data):
                powerbi_workspace_id = stages_data[idx].get("workspaceId")

                # Search for workspace in Odoo by workspace_id
                if powerbi_workspace_id:
                    workspace_record = self.env["powerbi.workspace"].search(
                        [("workspace_id", "=", powerbi_workspace_id)], limit=1
                    )

            # Prepare stage values
            stage_values = {
                "name": stage_name,
                "stage_order": stages_data[idx].get("order"),
                "pipeline_id": pipeline.id,
                "workspace_id": workspace_record.id if workspace_record else False,
            }

            # Check if stage already exists at this sequence
            if sequence in existing_by_sequence:
                # Update existing stage
                existing_stage = existing_by_sequence[sequence]
                existing_stage.write(stage_values)
                updated_count += 1

            else:
                # Create new stage
                self.env["powerbi.pipeline.stage"].create(stage_values)
                created_count += 1

        # Delete any extra stages beyond what we need
        extra_stages = self.env["powerbi.pipeline.stage"].search(
            [
                ("pipeline_id", "=", pipeline.id),
                ("sequence", ">", stages_count * 10),
            ]
        )

        if extra_stages:
            extra_stages.unlink()

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

    def action_test_connection(self):
        """Test the Power BI connection with current credentials"""
        self.ensure_one()

        # Validate required fields
        if not self.client_id or not self.client_secret or not self.tenant_id:
            raise UserError(
                _(
                    "Please fill in all authentication fields (Client ID, Client Secret, Tenant ID)."
                )
            )

        try:
            # Generate token to test connection
            token = self._generate_access_token()

            if token:
                self.write(
                    {
                        "state": "connected",
                        "connection_test_result": _(
                            "Connection successful! Authenticated with Power BI."
                        ),
                        "access_token": token,
                        "token_expiry": datetime.now() + timedelta(hours=1),
                    }
                )

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Success"),
                        "message": _("Connection to Power BI was successful!"),
                        "type": "success",
                        "sticky": False,
                    },
                }

        except Exception as e:
            error_message = str(e)
            _logger.error("Power BI connection test failed: %s", error_message)
            self.write(
                {
                    "state": "error",
                    "connection_test_result": f"Connection failed: {error_message}",
                }
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Failed"),
                    "message": error_message,
                    "type": "danger",
                    "sticky": True,
                },
            }

    def action_sync_workspaces(self):
        """Sync workspaces from Power BI"""
        self.ensure_one()

        if self.state != "connected":
            raise UserError(_("Please test and establish connection first."))

        try:
            # Check if token is valid
            if not self._is_token_valid():
                self._generate_access_token()

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            # Fetch workspaces from Power BI
            response = requests.post(
                "https://api.powerbi.com/v1.0/myorg/RefreshUserPermissions",
                headers=headers,
                timeout=30,
            )

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            # Fetch workspaces from Power BI
            response = requests.get(
                "https://api.powerbi.com/v1.0/myorg/groups", headers=headers, timeout=30
            )

            if response.status_code == 200:
                workspaces_data = response.json().get("value", [])

                # Create or update workspaces
                workspace_model = self.env["powerbi.workspace"]
                synced_count = 0

                for ws_data in workspaces_data:
                    workspace = workspace_model.search(
                        [
                            ("workspace_id", "=", ws_data.get("id")),
                            ("config_id", "=", self.id),
                        ],
                        limit=1,
                    )

                    vals = {
                        "workspace_name": ws_data.get("name"),
                        "workspace_id": ws_data.get("id"),
                        "config_id": self.id,
                        "state": "published",
                    }

                    if workspace:
                        workspace.write(vals)
                    else:
                        workspace_model.create(vals)

                    synced_count += 1

                self.write({"last_sync_date": fields.Datetime.now()})

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Sync Complete"),
                        "message": _("%s workspace(s) synced successfully.")
                        % synced_count,
                        "type": "success",
                        "sticky": False,
                    },
                }
            else:
                raise UserError(_("Failed to fetch workspaces: %s") % response.text)

        except Exception as e:
            _logger.error("Workspace sync failed: %s", str(e))
            raise UserError(_("Workspace sync failed: %s") % str(e))

    def action_generate_token(self):
        """Generate a new access token"""
        self.ensure_one()

        if not self.client_id or not self.client_secret or not self.tenant_id:
            raise UserError(_("Please fill in all authentication fields first."))

        try:
            token = self._generate_access_token()

            if token:
                self.write(
                    {
                        "access_token": token,
                        "token_expiry": datetime.now() + timedelta(hours=1),
                    }
                )

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Token Generated"),
                        "message": _("Access token generated successfully."),
                        "type": "success",
                        "sticky": False,
                    },
                }
        except Exception as e:
            raise UserError(_("Token generation failed: %s") % str(e))

    def action_view_workspaces(self):
        """Open workspaces view"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Workspaces"),
            "res_model": "powerbi.workspace",
            "view_mode": "list,form",
            "domain": [("config_id", "=", self.id)],
            "context": {"default_config_id": self.id},
            "target": "current",
        }

    def action_view_eventhouses(self):
        """Open eventhouses view"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Eventhouses"),
            "res_model": "powerbi.eventhouse",
            "view_mode": "list,form",
            "domain": [("config_id", "=", self.id)],
            "context": {"default_config_id": self.id},
            "target": "current",
        }

    def action_view_databases(self):
        """Open KQL databases view"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("KQL Databases"),
            "res_model": "powerbi.kql.database",
            "view_mode": "list,form",
            "domain": [("config_id", "=", self.id)],
            "context": {"default_config_id": self.id},
            "target": "current",
        }

    def action_view_tables(self):
        """Open tables view"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Tables"),
            "res_model": "powerbi.kql.table",
            "view_mode": "list,form",
            "domain": [("config_id", "=", self.id)],
            "context": {"default_config_id": self.id},
            "target": "current",
        }

    def action_view_datasets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Datasets"),
            "res_model": "powerbi.dataset",
            "view_mode": "list,form",
            "domain": [("config_id", "=", self.id)],
            "context": {"default_config_id": self.id},
            "target": "current",
        }

    def action_view_reports(self):
        """Open reports view"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reports"),
            "res_model": "powerbi.report",
            "view_mode": "list,form",
            "domain": [("config_id", "=", self.id)],
            "context": {"default_config_id": self.id},
            "target": "current",
        }

    def _generate_access_token(self):
        """Generate Power BI access token using ROPC password flow"""
        self.ensure_one()

        token_url = (
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        )

        data = {
            "grant_type": "client_credentials",  # ← back to this
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://analysis.windows.net/powerbi/api/.default",
        }

        try:
            response = requests.post(token_url, data=data, timeout=30)

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")

                if not access_token:
                    raise ValueError("No access token in response")

                return access_token

            else:
                error_msg = (
                    f"Token generation failed: {response.status_code} - {response.text}"
                )
                _logger.error(error_msg)
                raise ValueError(error_msg)

        except requests.exceptions.RequestException as e:
            _logger.error("Network error during token generation: %s", str(e))
            raise
        except Exception as e:
            _logger.error("Unexpected error during token generation: %s", str(e))
            raise

    def _is_token_valid(self):
        """Check if the current access token is still valid"""
        self.ensure_one()

        if not self.access_token or not self.token_expiry:
            return False

        # Add 5 minute buffer before actual expiry
        return datetime.now() < (self.token_expiry - timedelta(minutes=5))

    def _get_valid_token(self):
        """Get a valid access token, generating new one if needed"""
        self.ensure_one()

        if not self._is_token_valid():
            token = self._generate_access_token()
            self.write(
                {
                    "access_token": token,
                    "token_expiry": datetime.now() + timedelta(hours=1),
                }
            )
            return token

        return self.access_token

    @api.model
    def _cron_refresh_tokens(self):
        """Cron job to refresh expiring tokens"""
        configs = self.search([("state", "=", "connected"), ("active", "=", True)])

        for config in configs:
            try:
                if not config._is_token_valid():
                    config._get_valid_token()

            except Exception as e:
                _logger.error(
                    "Failed to refresh token for config %s: %s", config.name, str(e)
                )
                config.write({"state": "error"})
