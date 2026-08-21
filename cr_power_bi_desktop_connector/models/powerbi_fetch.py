# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)


class PowerBIConfigFetch(models.Model):
    _inherit = "powerbi.config"

    def _fetch_workspaces(self):
        """Internal method to fetch workspaces"""
        self.ensure_one()

        token = self._get_valid_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        response = requests.get(
            "https://api.powerbi.com/v1.0/myorg/groups", headers=headers, timeout=30
        )

        if response.status_code == 200:
            workspaces_data = response.json().get("value", [])
            workspace_model = self.env["powerbi.workspace"]
            count = 0

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
                count += 1

            return count

        return 0


class PowerBIWorkspaceFetch(models.Model):
    _inherit = "powerbi.workspace"

    def action_fetch_eventhouses(self):
        """Fetch eventhouses from Microsoft Fabric for this workspace"""
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
                f"https://api.fabric.microsoft.com/v1/workspaces/{self.workspace_id}/items",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                eventhouses_data = response.json().get("value", [])
                eventhouse_model = self.env["powerbi.eventhouse"]
                count = 0

                for eh_data in eventhouses_data:
                    if eh_data.get("type") != "Eventhouse":
                        continue
                    eventhouse = eventhouse_model.search(
                        [
                            ("eventhouse_id", "=", eh_data.get("id")),
                            ("workspace_id", "=", self.id),
                        ],
                        limit=1,
                    )

                    vals = {
                        "eventhouse_name": eh_data.get(
                            "displayName", eh_data.get("name")
                        ),
                        "eventhouse_id": eh_data.get("id"),
                        "description": eh_data.get("description"),
                        "workspace_id": self.id,
                        "config_id": self.config_id.id,
                        "state": "published",
                        "processing_status": eh_data.get("status", "Active"),
                        "created_on": fields.Datetime.now(),
                    }

                    if eventhouse:
                        eventhouse.write(vals)
                    else:
                        eventhouse_model.create(vals)
                    count += 1

                self.message_post(
                    body=_("%s eventhouse(s) fetched from Microsoft Fabric.") % count
                )

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Fetch Complete"),
                        "message": _("%s eventhouse(s) fetched successfully!") % count,
                        "type": "success",
                        "sticky": False,
                    },
                }
            else:
                raise UserError(_("Failed to fetch eventhouses: %s") % response.text)

        except Exception as e:
            _logger.error("Eventhouse fetch failed: %s", str(e))
            raise UserError(_("Eventhouse fetch failed: %s") % str(e))

    def action_fetch_datasets(self):
        """Fetch semantic models (datasets) from Power BI for this workspace"""
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
                f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id}/datasets",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                datasets_data = response.json().get("value", [])
                dataset_model = self.env["powerbi.dataset"]
                count = 0

                for ds_data in datasets_data:
                    dataset = dataset_model.search(
                        [
                            ("dataset_id", "=", ds_data.get("id")),
                            ("workspace_id", "=", self.id),
                        ],
                        limit=1,
                    )

                    vals = {
                        "dataset_name": ds_data.get("name"),
                        "dataset_id": ds_data.get("id"),
                        "workspace_id": self.id,
                        "config_id": self.config_id.id,
                        "state": "published",
                        "created_on": fields.Datetime.now(),
                    }

                    if dataset:
                        dataset.write(vals)
                    else:
                        dataset_model.create(vals)
                    count += 1

                self.message_post(
                    body=_("%s dataset(s) fetched from Power BI.") % count
                )

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Fetch Complete"),
                        "message": _("%s dataset(s) fetched successfully!") % count,
                        "type": "success",
                        "sticky": False,
                    },
                }
            else:
                raise UserError(_("Failed to fetch datasets: %s") % response.text)

        except Exception as e:
            _logger.error("Dataset fetch failed: %s", str(e))
            raise UserError(_("Dataset fetch failed: %s") % str(e))


class PowerBIEventhouseFetch(models.Model):
    _inherit = "powerbi.eventhouse"

    def action_fetch_databases(self):
        """Fetch KQL databases from Microsoft Fabric for this eventhouse"""
        self.ensure_one()

        if not self.eventhouse_id:
            raise UserError(_("Eventhouse must be published first."))

        try:
            token = self.config_id._get_valid_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"https://api.fabric.microsoft.com/v1/workspaces/{self.workspace_id.workspace_id}/kqlDatabases",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                databases_data = response.json().get("value", [])
                database_model = self.env["powerbi.kql.database"]
                count = 0

                for db_data in databases_data:
                    # CRITICAL: Only process databases that belong to THIS eventhouse
                    parent_eh_id = db_data.get("properties", {}).get(
                        "parentEventhouseItemId"
                    )

                    # Skip if parentEventhouseItemId doesn't match current eventhouse_id
                    if parent_eh_id != self.eventhouse_id:
                        continue

                    # Process only databases belonging to this eventhouse
                    database = database_model.search(
                        [
                            ("database_id", "=", db_data.get("id")),
                            ("eventhouse_id", "=", self.id),
                        ],
                        limit=1,
                    )

                    vals = {
                        "database_name": db_data.get(
                            "displayName", db_data.get("name")
                        ),
                        "database_id": db_data.get("id"),
                        "description": db_data.get("description"),
                        "query_service_uri": db_data.get("properties", {}).get(
                            "queryServiceUri"
                        ),
                        "ingestion_service_uri": db_data.get("properties", {}).get(
                            "ingestionServiceUri"
                        ),
                        "eventhouse_id": self.id,
                        "config_id": self.config_id.id,
                        "state": "published",
                        "created_on": fields.Datetime.now(),
                    }

                    if database:
                        database.write(vals)
                    else:
                        database_model.create(vals)
                    count += 1

                self.message_post(
                    body=_("%s database(s) fetched from Microsoft Fabric.") % count
                )

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Fetch Complete"),
                        "message": _("%s database(s) fetched successfully!") % count,
                        "type": "success",
                        "sticky": False,
                    },
                }
            else:
                raise UserError(_("Failed to fetch databases: %s") % response.text)

        except Exception as e:
            _logger.error("Database fetch failed: %s", str(e))
            raise UserError(_("Database fetch failed: %s") % str(e))
