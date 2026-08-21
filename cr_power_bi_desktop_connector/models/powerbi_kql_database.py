# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class PowerBIKQLDatabase(models.Model):
    _name = "powerbi.kql.database"
    _description = "Power BI KQL Database"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "database_name"
    _order = "create_date desc"

    # Basic Information
    database_name = fields.Char(string="Database Name", required=True)
    database_id = fields.Char(string="Database ID", readonly=True)

    # Relations
    config_id = fields.Many2one(
        "powerbi.config", string="Configuration", required=True, ondelete="cascade"
    )
    eventhouse_id = fields.Many2one(
        "powerbi.eventhouse", string="Eventhouse", required=True, ondelete="cascade"
    )
    workspace_id = fields.Many2one(
        "powerbi.workspace",
        string="Workspace",
        related="eventhouse_id.workspace_id",
        store=True,
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

    # Service URLs
    query_service_uri = fields.Char(string="Query Service URI", readonly=True)
    ingestion_service_uri = fields.Char(string="Ingestion Service URI", readonly=True)

    # Power BI Metadata
    created_by = fields.Char(string="Created By", readonly=True)
    created_on = fields.Datetime(string="Created On", readonly=True)
    last_updated_on = fields.Datetime(string="Last Updated", readonly=True)

    # Description
    description = fields.Text(string="Description")

    def action_create_database(self):
        """Create KQL database within Eventhouse in Microsoft Fabric"""
        self.ensure_one()

        if not self.database_name:
            raise UserError(_("Please provide a database name."))

        if not self.eventhouse_id.eventhouse_id:
            raise UserError(_("Eventhouse must be published first."))

        try:
            token = self.config_id._get_valid_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Create database with proper creationPayload structure
            data = {
                "displayName": self.database_name,
                "description": self.description or "A KQL database",
                "creationPayload": {
                    "databaseType": "ReadWrite",
                    "parentEventhouseItemId": self.eventhouse_id.eventhouse_id,
                },
            }

            # Use the correct kqlDatabases endpoint
            response = requests.post(
                f"https://api.fabric.microsoft.com/v1/workspaces/{self.workspace_id.workspace_id}/kqlDatabases",
                headers=headers,
                json=data,
                timeout=30,
            )

            if response.status_code == 202:
                # Async creation - show success notification immediately

                # Show success notification to user
                self.env["bus.bus"]._sendone(
                    self.env.user.partner_id,
                    "simple_notification",
                    {
                        "type": "success",
                        "title": _("Database Created!"),
                        "message": _(
                            'KQL Database "%s" created successfully. Fetching details...'
                        )
                        % self.database_name,
                        "sticky": False,
                    },
                )

                eventhouse = self.eventhouse_id

                # Delete the current draft record
                self.unlink()

                # Wait for database to be created
                import time

                time.sleep(5)  # Wait 5 seconds

                # Call fetch_databases on the eventhouse to get the newly created database
                return eventhouse.action_fetch_databases()

            elif response.status_code in [200, 201]:
                # Immediate creation
                database_data = response.json()

                self.write(
                    {
                        "database_id": database_data.get("id"),
                        "query_service_uri": database_data.get("properties", {}).get(
                            "queryServiceUri"
                        ),
                        "ingestion_service_uri": database_data.get(
                            "properties", {}
                        ).get("ingestionServiceUri"),
                        "state": "published",
                        "created_on": fields.Datetime.now(),
                        "last_updated_on": fields.Datetime.now(),
                    }
                )

                self.message_post(
                    body=_("KQL Database created successfully within Eventhouse.")
                )

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Success"),
                        "message": _("KQL Database created in Eventhouse!"),
                        "type": "success",
                        "sticky": False,
                    },
                }
            else:
                error_msg = f"Failed to create database: {response.status_code} - {response.text}"
                _logger.error(error_msg)
                self.write({"state": "error"})
                raise UserError(_(error_msg))

        except Exception as e:
            _logger.error("Database creation failed: %s", str(e))
            self.write({"state": "error"})
            raise UserError(_("Database creation failed: %s") % str(e))

    def action_sync_database(self):
        """Sync database details from Microsoft Fabric"""
        self.ensure_one()

        if not self.database_id:
            raise UserError(_("No database ID found. Please create database first."))

        try:
            token = self.config_id._get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"https://api.fabric.microsoft.com/v1/workspaces/{self.workspace_id.workspace_id}/kqlDatabases/{self.database_id}",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                database_data = response.json()
                properties = database_data.get("properties", {})

                self.write(
                    {
                        "database_name": database_data.get(
                            "displayName", self.database_name
                        ),
                        "description": database_data.get(
                            "description", self.description
                        ),
                        "query_service_uri": properties.get(
                            "queryServiceUri", self.query_service_uri
                        ),
                        "ingestion_service_uri": properties.get(
                            "ingestionServiceUri", self.ingestion_service_uri
                        ),
                        "last_updated_on": fields.Datetime.now(),
                    }
                )

                self.message_post(body=_("Database synced from Microsoft Fabric."))

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Success"),
                        "message": _("Database synced successfully!"),
                        "type": "success",
                        "sticky": False,
                    },
                }
            else:
                raise UserError(_("Failed to sync database: %s") % response.text)

        except Exception as e:
            _logger.error("Database sync failed: %s", str(e))
            raise UserError(_("Database sync failed: %s") % str(e))
