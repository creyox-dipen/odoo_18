# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class PowerBIDataset(models.Model):
    _name = "powerbi.dataset"
    _description = "Power BI Dataset (Semantic Model)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "dataset_name"
    _order = "create_date desc"

    # Basic Information
    dataset_name = fields.Char(string="Dataset Name", required=True)
    dataset_id = fields.Char(string="Dataset ID", readonly=True)
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

    # Source Database
    database_id = fields.Many2one("powerbi.kql.database", string="Source KQL Database")

    # Status Fields
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("to_publish", "To Publish"),
            ("published", "Published"),
            ("refreshing", "Refreshing"),
            ("error", "Error"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    # Power BI Metadata
    created_by = fields.Char(string="Created By", readonly=True)
    created_on = fields.Datetime(string="Created On", readonly=True)

    last_refresh_date = fields.Datetime(string="Last Refresh Date", readonly=True)
    last_refresh_status = fields.Selection(
        [("success", "Success"), ("failed", "Failed"), ("pending", "Pending")],
        string="Last Refresh Status",
        readonly=True,
    )

    next_refresh_date = fields.Datetime(string="Next Scheduled Refresh", readonly=True)

    # One2many for reports using this dataset
    report_ids = fields.One2many("powerbi.report", "dataset_id", string="Reports")

    def action_refresh_dataset(self):
        """Trigger dataset refresh in Power BI"""
        self.ensure_one()

        if self.state != "published":
            raise UserError(_("Dataset must be published first."))

        if not self.dataset_id:
            raise UserError(_("No dataset ID found."))

        try:
            token = self.config_id._get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id.workspace_id}/datasets/{self.dataset_id}/refreshes",
                headers=headers,
                json={"notifyOption": "NoNotification"},
                timeout=30,
            )

            if response.status_code in [200, 202]:
                self.write(
                    {
                        "state": "refreshing",
                        "last_refresh_status": "pending",
                        "last_refresh_date": fields.Datetime.now(),
                    }
                )

                self.message_post(body=_("Dataset refresh initiated."))

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Refresh Started"),
                        "message": _("Dataset refresh initiated successfully!"),
                        "type": "info",
                        "sticky": False,
                    },
                }
            else:
                raise UserError(_("Failed to refresh dataset: %s") % response.text)

        except Exception as e:
            _logger.error("Dataset refresh failed: %s", str(e))
            raise UserError(_("Dataset refresh failed: %s") % str(e))

    def action_configure_refresh(self):
        """Configure scheduled refresh settings"""
        self.ensure_one()

        if self.state != "published":
            raise UserError(_("Dataset must be published first."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Configure Refresh Schedule"),
            "res_model": "powerbi.dataset.refresh.wizard",
            "view_mode": "form",
            "context": {"default_dataset_id": self.id},
            "target": "new",
        }

    def action_view_reports(self):
        """Open reports view"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reports"),
            "res_model": "powerbi.report",
            "view_mode": "list,form",
            "domain": [("dataset_id", "=", self.id)],
            "context": {
                "default_dataset_id": self.id,
                "default_workspace_id": self.workspace_id.id,
            },
            "target": "current",
        }
