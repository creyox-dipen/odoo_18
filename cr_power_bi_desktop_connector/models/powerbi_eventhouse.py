# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class PowerBIEventhouse(models.Model):
    _name = "powerbi.eventhouse"
    _description = "Power BI Eventhouse"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "eventhouse_name"
    _order = "create_date desc"

    # Basic Information
    eventhouse_name = fields.Char(string="Eventhouse Name", required=True)
    eventhouse_id = fields.Char(string="Eventhouse ID", readonly=True)
    description = fields.Text(string="Description")

    # Relations
    config_id = fields.Many2one(
        "powerbi.config", string="Configuration", required=True, ondelete="cascade"
    )
    workspace_id = fields.Many2one(
        "powerbi.workspace", string="Workspace", required=True, ondelete="cascade"
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

    # Monitoring Fields
    data_scaling_info = fields.Text(string="Data Scaling Info", readonly=True)
    processing_status = fields.Char(string="Processing Status", readonly=True)

    # Counters for Smart Buttons
    database_count = fields.Integer(
        string="Databases", compute="_compute_counts", store=True
    )

    # One2many Relations
    database_ids = fields.One2many(
        "powerbi.kql.database", "eventhouse_id", string="KQL Databases"
    )

    @api.depends("database_ids")
    def _compute_counts(self):
        for record in self:
            record.database_count = len(record.database_ids)

    def action_create_eventhouse(self):
        """Create eventhouse in Microsoft Fabric"""
        self.ensure_one()

        if not self.eventhouse_name:
            raise UserError(_("Please provide an eventhouse name."))

        if not self.workspace_id.workspace_id:
            raise UserError(_("Workspace must be published to Power BI first."))

        try:
            token = self.config_id._get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Microsoft Fabric API endpoint for creating eventhouse
            data = {
                "displayName": self.eventhouse_name,
                "description": self.description or "",
            }

            # Note: This is a placeholder endpoint - actual Fabric API may differ
            response = requests.post(
                f"https://api.fabric.microsoft.com/v1/workspaces/{self.workspace_id.workspace_id}/eventhouses",
                headers=headers,
                json=data,
                timeout=30,
            )

            if response.status_code in [200, 201]:
                eventhouse_data = response.json()

                self.write(
                    {
                        "eventhouse_id": eventhouse_data.get("id"),
                        "state": "published",
                        "created_on": fields.Datetime.now(),
                        "last_updated_on": fields.Datetime.now(),
                        "processing_status": "Active",
                    }
                )

                self.message_post(
                    body=_("Eventhouse created successfully in Microsoft Fabric.")
                )

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Success"),
                        "message": _("Eventhouse created successfully!"),
                        "type": "success",
                        "sticky": False,
                    },
                }
            else:
                error_msg = f"Failed to create eventhouse: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self.write({"state": "error"})
                raise UserError(_(error_msg))

        except Exception as e:
            _logger.error("Eventhouse creation failed: %s", str(e))
            self.write({"state": "error"})
            raise UserError(_("Eventhouse creation failed: %s") % str(e))

    def action_publish(self):
        """Mark eventhouse as ready to publish"""
        self.ensure_one()
        self.write({"state": "to_publish"})
        self.message_post(body=_("Eventhouse marked for publishing."))

    def action_sync_eventhouse(self):
        """Sync eventhouse details from Microsoft Fabric"""
        self.ensure_one()

        if not self.eventhouse_id:
            raise UserError(
                _("No eventhouse ID found. Please create eventhouse first.")
            )

        try:
            token = self.config_id._get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"https://api.fabric.microsoft.com/v1/workspaces/{self.workspace_id.workspace_id}/eventhouses/{self.eventhouse_id}",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                eventhouse_data = response.json()

                self.write(
                    {
                        "eventhouse_name": eventhouse_data.get(
                            "displayName", self.eventhouse_name
                        ),
                        "description": eventhouse_data.get(
                            "description", self.description
                        ),
                        "last_updated_on": fields.Datetime.now(),
                        "processing_status": eventhouse_data.get("status", "Unknown"),
                    }
                )

                self.message_post(body=_("Eventhouse synced from Microsoft Fabric."))

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Success"),
                        "message": _("Eventhouse synced successfully!"),
                        "type": "success",
                        "sticky": False,
                    },
                }
            else:
                raise UserError(_("Failed to sync eventhouse: %s") % response.text)

        except Exception as e:
            _logger.error("Eventhouse sync failed: %s", str(e))
            raise UserError(_("Eventhouse sync failed: %s") % str(e))

    def action_monitor_scaling(self):
        """Monitor data scaling and processing status"""
        self.ensure_one()

        if not self.eventhouse_id:
            raise UserError(_("No eventhouse ID found."))

        try:
            token = self.config_id._get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Get monitoring metrics
            response = requests.get(
                f"https://api.fabric.microsoft.com/v1/workspaces/{self.workspace_id.workspace_id}/eventhouses/{self.eventhouse_id}/metrics",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                metrics_data = response.json()

                scaling_info = f"""
        Data Volume: {metrics_data.get('dataVolume', 'N/A')}
        Throughput: {metrics_data.get('throughput', 'N/A')}
        Storage Used: {metrics_data.get('storageUsed', 'N/A')}
        Active Connections: {metrics_data.get('activeConnections', 'N/A')}
                        """

                self.write(
                    {
                        "data_scaling_info": scaling_info.strip(),
                        "processing_status": metrics_data.get("status", "Active"),
                        "last_updated_on": fields.Datetime.now(),
                    }
                )

                self.message_post(body=_("Monitoring data updated."))

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Monitoring Updated"),
                        "message": _("Scaling metrics retrieved successfully!"),
                        "type": "info",
                        "sticky": False,
                    },
                }
            else:
                raise UserError(_("Failed to get metrics: %s") % response.text)

        except Exception as e:
            _logger.error("Monitoring failed: %s", str(e))
            raise UserError(_("Monitoring failed: %s") % str(e))

    def action_view_databases(self):
        """Open KQL databases view"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("KQL Databases"),
            "res_model": "powerbi.kql.database",
            "view_mode": "list,form",
            "domain": [("eventhouse_id", "=", self.id)],
            "context": {
                "default_eventhouse_id": self.id,
                "default_workspace_id": self.workspace_id.id,
                "default_config_id": self.config_id.id,
            },
            "target": "current",
        }
