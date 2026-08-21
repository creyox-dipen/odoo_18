# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class PowerBIWorkspace(models.Model):
    _name = "powerbi.workspace"
    _description = "Power BI Workspace"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "workspace_name"
    _order = "create_date desc"

    # Basic Information
    workspace_name = fields.Char(string="Workspace Name", required=True)
    workspace_id = fields.Char(string="Workspace ID", readonly=True)
    description = fields.Text(string="Description")

    # Relations
    config_id = fields.Many2one(
        "powerbi.config", string="Configuration", required=True, ondelete="cascade"
    )
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
    )

    # Power BI Metadata
    created_by = fields.Char(string="Created By", readonly=True)
    created_on = fields.Datetime(string="Created On", readonly=True)
    last_updated_on = fields.Datetime(string="Last Updated", readonly=True)

    # Counters for Smart Buttons
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

    # One2many Relations
    database_ids = fields.One2many(
        "powerbi.kql.database", "workspace_id", string="KQLDatabases"
    )
    eventhouse_ids = fields.One2many(
        "powerbi.eventhouse", "workspace_id", string="Eventhouses"
    )
    dataset_ids = fields.One2many("powerbi.dataset", "workspace_id", string="Datasets")
    report_ids = fields.One2many("powerbi.report", "workspace_id", string="Reports")

    @api.depends(
        "eventhouse_ids", "eventhouse_ids.database_ids", "dataset_ids", "report_ids"
    )
    def _compute_counts(self):
        for record in self:
            record.eventhouse_count = len(record.eventhouse_ids)
            record.dataset_count = len(record.dataset_ids)
            record.report_count = len(record.report_ids)
            record.database_count = sum(
                len(eh.database_ids) for eh in record.eventhouse_ids
            )

    def action_create_workspace(self):
        """Create workspace in Power BI"""
        self.ensure_one()

        if not self.workspace_name:
            raise UserError(_("Please provide a workspace name."))

        try:
            token = self.config_id._get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            try:
                refresh_response = requests.post(
                    "https://api.powerbi.com/v1.0/myorg/RefreshUserPermissions",
                    headers=headers,
                    timeout=30,
                )

            except Exception as refresh_error:
                _logger.warning(
                    "Failed to refresh permissions (non-critical): %s",
                    str(refresh_error),
                )

            # Step 2: Create Workspace
            data = {"name": self.workspace_name}

            response = requests.post(
                "https://api.powerbi.com/v1.0/myorg/groups",
                headers=headers,
                json=data,
                timeout=30,
            )

            if response.status_code == 200:
                workspace_data = response.json()

                self.write(
                    {
                        "workspace_id": workspace_data.get("id"),
                        "state": "published",
                        "created_on": fields.Datetime.now(),
                        "last_updated_on": fields.Datetime.now(),
                    }
                )

                self.message_post(body=_("Workspace created successfully in Power BI."))

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Success"),
                        "message": _("Workspace created in Power BI successfully!"),
                        "type": "success",
                        "sticky": False,
                    },
                }

            elif response.status_code == 401:
                error_msg = "Authentication failed. Please check your Power BI credentials and try refreshing permissions."
                _logger.error(error_msg)
                self.write({"state": "error"})
                raise UserError(_(error_msg))

            elif response.status_code == 403:
                error_msg = "Access denied. You may not have permission to create workspaces. Try refreshing permissions or contact your administrator."
                _logger.error(error_msg)
                self.write({"state": "error"})
                raise UserError(_(error_msg))

            elif response.status_code == 409:
                error_msg = f'A workspace named "{self.workspace_name}" already exists in Power BI.'
                _logger.error(error_msg)
                self.write({"state": "error"})
                raise UserError(_(error_msg))

            else:
                error_msg = f"Failed to create workspace: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self.write({"state": "error"})
                raise UserError(_(error_msg))

        except requests.exceptions.Timeout:
            error_msg = "Request timed out. Please try again."
            _logger.error(error_msg)
            self.write({"state": "error"})
            raise UserError(_(error_msg))

        except requests.exceptions.ConnectionError:
            error_msg = (
                "Could not connect to Power BI. Please check your internet connection."
            )
            _logger.error(error_msg)
            self.write({"state": "error"})
            raise UserError(_(error_msg))

        except Exception as e:
            _logger.error("Workspace creation failed: %s", str(e))
            self.write({"state": "error"})
            raise UserError(_("Workspace creation failed: %s") % str(e))

    def action_publish(self):
        """Mark workspace as ready to publish"""
        self.ensure_one()
        self.write({"state": "to_publish"})
        self.message_post(body=_("Workspace marked for publishing."))

    def action_fetch_workspace(self):
        """Sync workspace details from Power BI"""

        self.ensure_one()

        if not self.workspace_id:
            raise UserError(
                _("No workspace ID found. Please create workspace in Power BI first.")
            )

        try:
            token = self.config_id._get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id}",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                workspace_data = response.json()

                self.write(
                    {
                        "workspace_name": workspace_data.get(
                            "name", self.workspace_name
                        ),
                        "last_updated_on": fields.Datetime.now(),
                    }
                )

                self.message_post(body=_("Workspace synced from Power BI."))

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Success"),
                        "message": _("Workspace synced successfully!"),
                        "type": "success",
                        "sticky": False,
                    },
                }
            else:
                raise UserError(_("Failed to fetch workspace: %s") % response.text)

        except Exception as e:
            _logger.error("Workspace sync failed: %s", str(e))
            raise UserError(_("Workspace sync failed: %s") % str(e))

    def action_view_eventhouses(self):
        """Open eventhouses view"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Eventhouses"),
            "res_model": "powerbi.eventhouse",
            "view_mode": "list,form",
            "domain": [("workspace_id", "=", self.id)],
            "context": {
                "default_workspace_id": self.id,
                "default_config_id": self.config_id.id,
            },
            "target": "current",
        }

    def action_view_databases(self):
        """Open KQL databases view"""
        self.ensure_one()
        database_ids = self.eventhouse_ids.mapped("database_ids").ids
        return {
            "type": "ir.actions.act_window",
            "name": _("KQL Databases"),
            "res_model": "powerbi.kql.database",
            "view_mode": "list,form",
            "domain": [("id", "in", database_ids)],
            "context": {"default_config_id": self.config_id.id},
            "target": "current",
        }

    def action_view_datasets(self):
        """Open datasets view"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Datasets"),
            "res_model": "powerbi.dataset",
            "view_mode": "list,form",
            "domain": [("workspace_id", "=", self.id)],
            "context": {
                "default_workspace_id": self.id,
                "default_config_id": self.config_id.id,
            },
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
            "domain": [("workspace_id", "=", self.id)],
            "context": {
                "default_workspace_id": self.id,
                "default_config_id": self.config_id.id,
            },
            "target": "current",
        }

    def action_fetch_reports(self):
        """Fetch reports from Power BI for this workspace"""
        self.ensure_one()

        if not self.workspace_id:
            raise UserError(_("Workspace must be published to Power BI first."))

        try:
            token = self.config_id._get_valid_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id}/reports",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                reports_data = response.json().get("value", [])
                report_model = self.env["powerbi.report"]
                count = 0

                for rp_data in reports_data:
                    report = report_model.search(
                        [
                            ("report_id", "=", rp_data.get("id")),
                            ("workspace_id", "=", self.id),
                        ],
                        limit=1,
                    )

                    vals = {
                        "report_name": rp_data.get("name"),
                        "report_id": rp_data.get("id"),
                        "web_url": rp_data.get("webUrl"),
                        "embed_url": rp_data.get("embedUrl"),
                        "workspace_id": self.id,
                        "config_id": self.config_id.id,
                        "state": "published",
                    }

                    if report:
                        report.write(vals)
                    else:
                        report_model.create(vals)
                    count += 1

                self.message_post(body=_("%s report(s) fetched from Power BI.") % count)

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Fetch Complete"),
                        "message": _("%s report(s) fetched successfully!") % count,
                        "type": "success",
                        "sticky": False,
                    },
                }
            else:
                raise UserError(_("Failed to fetch reports: %s") % response.text)

        except Exception as e:
            _logger.error("Report fetch failed: %s", str(e))
            raise UserError(_("Report fetch failed: %s") % str(e))

    def action_fetch_dashboards(self):
        """Fetch dashboards from Power BI for this workspace"""
        self.ensure_one()
        if not self.workspace_id:
            raise UserError(_("Workspace must be published to Power BI first."))
        try:
            token = self.config_id._get_valid_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Step 1: Pre-fetch all datasets from Power BI and ensure they exist in Odoo
            # This ensures tiles can always be linked to a dataset record
            datasets_response = requests.get(
                f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id}/datasets",
                headers=headers,
                timeout=30,
            )
            if datasets_response.status_code == 200:
                for ds_data in datasets_response.json().get("value", []):
                    pbi_dataset_id = ds_data.get("id")
                    if not pbi_dataset_id:
                        continue
                    existing = self.env["powerbi.dataset"].search(
                        [
                            ("dataset_id", "=", pbi_dataset_id),
                            ("workspace_id", "=", self.id),
                        ],
                        limit=1,
                    )
                    if not existing:
                        self.env["powerbi.dataset"].create(
                            {
                                "dataset_name": ds_data.get("name", "Unknown Dataset"),
                                "dataset_id": pbi_dataset_id,
                                "workspace_id": self.id,
                                "config_id": self.config_id.id,
                                "state": "published",
                            }
                        )

            else:
                _logger.warning(
                    "Could not pre-fetch datasets: %s", datasets_response.text
                )

            # Step 2: Fetch dashboards
            response = requests.get(
                f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id}/dashboards",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                dashboards_data = response.json().get("value", [])
                dashboard_model = self.env["powerbi.dashboard"]
                tile_model = self.env["powerbi.dashboard.tile"]
                count = 0

                for db_data in dashboards_data:
                    dashboard = dashboard_model.search(
                        [
                            ("dashboard_id", "=", db_data.get("id")),
                            ("workspace_id", "=", self.id),
                        ],
                        limit=1,
                    )
                    vals = {
                        "dashboard_name": db_data.get("displayName"),
                        "dashboard_id": db_data.get("id"),
                        "web_url": db_data.get("webUrl"),
                        "embed_url": db_data.get("embedUrl"),
                        "workspace_id": self.id,
                        "config_id": self.config_id.id,
                        "state": "published",
                    }
                    if dashboard:
                        dashboard.write(vals)
                    else:
                        dashboard = dashboard_model.create(vals)
                    count += 1

                    # Step 3: Fetch tiles
                    tiles_response = requests.get(
                        f'https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id}/dashboards/{db_data.get("id")}/tiles',
                        headers=headers,
                        timeout=30,
                    )

                    if tiles_response.status_code == 200:
                        tiles_data = tiles_response.json().get("value", [])
                        tile_model.search(
                            [("dashboard_id", "=", dashboard.id)]
                        ).unlink()

                        for tile_data in tiles_data:
                            tile_vals = {
                                "dashboard_id": dashboard.id,
                                "tile_id": tile_data.get("id"),
                                "tile_title": tile_data.get("title")
                                or tile_data.get("name")
                                or "Untitled",
                                "subtitle": tile_data.get("subTitle"),
                                "embed_url": tile_data.get("embedUrl"),
                            }

                            # Link report
                            report_id = tile_data.get("reportId")
                            if report_id:
                                report = self.env["powerbi.report"].search(
                                    [
                                        ("report_id", "=", report_id),
                                        ("workspace_id", "=", self.id),
                                    ],
                                    limit=1,
                                )
                                if report:
                                    tile_vals["report_id"] = report.id

                            # Link dataset — now guaranteed to exist after Step 1
                            pbi_dataset_id = tile_data.get("datasetId")
                            if pbi_dataset_id:
                                dataset = self.env["powerbi.dataset"].search(
                                    [
                                        ("dataset_id", "=", pbi_dataset_id),
                                        ("workspace_id", "=", self.id),
                                    ],
                                    limit=1,
                                )
                                if dataset:
                                    tile_vals["dataset_id"] = dataset.id

                                else:
                                    _logger.warning(
                                        "Dataset %s still not found after pre-fetch!",
                                        pbi_dataset_id,
                                    )

                            tile_model.create(tile_vals)

                    else:
                        _logger.warning(
                            "Failed to fetch tiles for dashboard %s: %s",
                            db_data.get("id"),
                            tiles_response.text,
                        )

                self.message_post(
                    body=_("%s dashboard(s) fetched from Power BI.") % count
                )
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Fetch Complete"),
                        "message": _("%s dashboard(s) fetched successfully!") % count,
                        "type": "success",
                        "sticky": False,
                    },
                }
            else:
                raise UserError(_("Failed to fetch dashboards: %s") % response.text)
        except Exception as e:
            _logger.error("Dashboard fetch failed: %s", str(e))
            raise UserError(_("Dashboard fetch failed: %s") % str(e))
