# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)


class PowerBIDashboard(models.Model):
    _name = "powerbi.dashboard"
    _description = "Power BI Dashboard"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "dashboard_name"
    _order = "create_date desc"

    # Basic Information
    dashboard_name = fields.Char(string="Dashboard Name", required=True, tracking=True)
    dashboard_id = fields.Char(string="Dashboard ID", readonly=True, copy=False)
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
    company_id = fields.Many2one(
        "res.company", string="Company", related="config_id.company_id", store=True
    )

    # Status Fields
    state = fields.Selection(
        [("draft", "Draft"), ("published", "Published"), ("archived", "Archived")],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    # Power BI Metadata
    created_by = fields.Char(string="Created By", readonly=True)
    created_on = fields.Datetime(string="Created On", readonly=True)

    # Tiles/Reports
    tile_ids = fields.One2many("powerbi.dashboard.tile", "dashboard_id", string="Tiles")
    tile_count = fields.Integer(
        string="Tiles", compute="_compute_tile_count", store=True
    )

    # Display Settings
    is_featured = fields.Boolean(
        string="Featured Dashboard", default=False, tracking=True
    )

    @api.depends("tile_ids")
    def _compute_tile_count(self):
        for record in self:
            record.tile_count = len(record.tile_ids)

    def action_publish(self):
        """Publish dashboard"""
        self.ensure_one()

        if not self.workspace_id.workspace_id:
            raise UserError(_("Workspace must be published first."))

        self.write({"state": "published", "created_on": fields.Datetime.now()})

        self.message_post(body=_("Dashboard published."))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Published"),
                "message": _("Dashboard published successfully!"),
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_dashboard(self):
        """Open dashboard in Power BI web"""
        self.ensure_one()

        if not self.web_url:
            raise UserError(
                _("No web URL available. Please sync dashboard from Power BI first.")
            )

        return {
            "type": "ir.actions.act_url",
            "url": self.web_url,
            "target": "new",
        }

    def get_dashboard_embed_data(self):
        self.ensure_one()
        try:
            token = self.config_id._get_valid_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Verify dashboard exists
            dashboard_response = requests.get(
                f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id.workspace_id}/dashboards/{self.dashboard_id}",
                headers=headers,
                timeout=30,
            )
            if dashboard_response.status_code != 200:
                return {
                    "error": f"Failed to get dashboard details: {dashboard_response.text}"
                }

            # Build clean embedUrl with groupId — required for token validation
            embed_url = (
                f"https://app.powerbi.com/dashboardEmbed"
                f"?dashboardId={self.dashboard_id}"
                f"&groupId={self.workspace_id.workspace_id}"
            )

            # Collect dataset IDs from stored tiles
            dataset_ids = list(
                {
                    tile.dataset_id.dataset_id
                    for tile in self.tile_ids
                    if tile.dataset_id and tile.dataset_id.dataset_id
                }
            )

            if not dataset_ids:
                return {
                    "error": "No datasets linked to tiles. Please re-fetch the dashboard.",
                    "web_url": self.web_url,
                }

            token_data = {
                "datasets": [{"id": ds_id} for ds_id in dataset_ids],
                "dashboards": [{"id": self.dashboard_id}],
                "targetWorkspaces": [{"id": self.workspace_id.workspace_id}],
            }

            token_response = requests.post(
                "https://api.powerbi.com/v1.0/myorg/GenerateToken",
                headers=headers,
                json=token_data,
                timeout=30,
            )

            if token_response.status_code != 200:
                return {
                    "error": f"Failed to generate embed token: {token_response.text}"
                }

            return {
                "token": token_response.json().get("token"),
                "embed_url": embed_url,
                "dashboard_id": self.dashboard_id,
                "web_url": self.web_url,
                "token_type": "Embed",
                "dataset_ids": dataset_ids,
            }

        except Exception as e:
            _logger.error("get_dashboard_embed_data failed: %s", str(e))
            return {"error": str(e)}

    def action_archive(self):
        """Archive dashboard"""
        self.ensure_one()

        self.write({"state": "archived"})
        self.message_post(body=_("Dashboard archived."))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Archived"),
                "message": _("Dashboard archived successfully!"),
                "type": "info",
                "sticky": False,
            },
        }

    def action_unarchive(self):
        """Restore archived dashboard"""
        self.ensure_one()

        self.write({"state": "published"})
        self.message_post(body=_("Dashboard restored from archive."))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Restored"),
                "message": _("Dashboard restored successfully!"),
                "type": "success",
                "sticky": False,
            },
        }

    def action_view_tiles(self):
        """Open tiles view"""
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Dashboard Tiles"),
            "res_model": "powerbi.dashboard.tile",
            "view_mode": "list,form",
            "domain": [("dashboard_id", "=", self.id)],
            "context": {"default_dashboard_id": self.id},
            "target": "current",
        }

    def action_sync_from_powerbi(self):
        """Sync dashboard details from Power BI"""
        self.ensure_one()

        if not self.dashboard_id:
            raise UserError(_("No dashboard ID found."))

        try:
            token = self.config_id._get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id.workspace_id}/dashboards/{self.dashboard_id}",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                dashboard_data = response.json()

                self.write(
                    {
                        "dashboard_name": dashboard_data.get(
                            "displayName", self.dashboard_name
                        ),
                        "web_url": dashboard_data.get("webUrl"),
                        "embed_url": dashboard_data.get("embedUrl"),
                    }
                )

                # Sync tiles
                self._sync_tiles_from_powerbi(dashboard_data.get("tiles", []))

                self.message_post(body=_("Dashboard synced from Power BI."))

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Success"),
                        "message": _("Dashboard synced successfully!"),
                        "type": "success",
                        "sticky": False,
                    },
                }
            else:
                raise UserError(_("Failed to sync dashboard: %s") % response.text)

        except Exception as e:
            _logger.error("Dashboard sync failed: %s", str(e))
            raise UserError(_("Dashboard sync failed: %s") % str(e))

    def action_toggle_featured(self):
        """Toggle featured status"""
        self.ensure_one()

        self.is_featured = not self.is_featured

        status = "featured" if self.is_featured else "unfeatured"
        self.message_post(body=_("Dashboard marked as %s.") % status)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Updated"),
                "message": _("Dashboard %s!") % status,
                "type": "success",
                "sticky": False,
            },
        }

    def action_embed_dashboard(self):
        self.ensure_one()
        if not self.dashboard_id:
            raise UserError(_("No dashboard ID available."))

        viewer = self.env["powerbi.dashboard.viewer"].create(
            {
                "dashboard_id": self.id,
                "embed_url": self.embed_url or "",
                "web_url": self.web_url or "",
                "dashboard_name": self.dashboard_name,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": self.dashboard_name,
            "res_model": "powerbi.dashboard.viewer",
            "res_id": viewer.id,
            "view_mode": "form",
            "target": "current",  # ← changed from 'new' to 'current'
            "flags": {"mode": "readonly"},
        }

    def _sync_tiles_from_powerbi(self, tiles_data):
        """Sync tiles from Power BI dashboard"""
        self.ensure_one()

        # Clear existing tiles
        self.tile_ids.unlink()

        # Create new tiles
        tile_model = self.env["powerbi.dashboard.tile"]

        for tile_data in tiles_data:
            tile_model.create(
                {
                    "dashboard_id": self.id,
                    "tile_title": tile_data.get("title", "Untitled"),
                    "tile_id": tile_data.get("id"),
                    "embed_url": tile_data.get("embedUrl"),
                    "subtitle": tile_data.get("subtitle"),
                }
            )

    @api.model
    def get_featured_dashboards(self):
        """Get all featured dashboards for current user"""
        domain = [("is_featured", "=", True), ("state", "=", "published")]

        dashboards = self.search(domain)

        # Filter by user access
        accessible_dashboards = []
        for dashboard in dashboards:
            if self.check_user_access(dashboard.id):
                accessible_dashboards.append(dashboard)

        return self.browse([d.id for d in accessible_dashboards])

    @api.model
    def check_user_access(self, dashboard_id):
        """Check if current user has access to dashboard"""
        dashboard = self.browse(dashboard_id)

        if not dashboard.exists():
            return False

        # If no specific users/groups defined, allow all
        if not dashboard.user_ids and not dashboard.group_ids:
            return True

        # Check user access
        if self.env.user in dashboard.user_ids:
            return True

        # Check group access
        user_groups = self.env.user.groups_id
        if any(group in dashboard.group_ids for group in user_groups):
            return True

        return False


class PowerBIDashboardTile(models.Model):
    _name = "powerbi.dashboard.tile"
    _description = "Power BI Dashboard Tile"
    _rec_name = "tile_title"
    _order = "sequence, id"

    # Basic Information
    sequence = fields.Integer(string="Sequence", default=10)
    tile_title = fields.Char(string="Tile Title", required=True)
    tile_id = fields.Char(string="Tile ID", readonly=True)
    dashboard_id = fields.Many2one(
        "powerbi.dashboard", string="Dashboard", required=True, ondelete="cascade"
    )

    # Tile Configuration
    report_id = fields.Many2one("powerbi.report", string="Source Report")
    dataset_id = fields.Many2one("powerbi.dataset", string="Source Dataset")

    # Embedding
    embed_url = fields.Char(string="Embed URL", readonly=True)

    # Description
    subtitle = fields.Char(string="Subtitle")

    def action_open_tile(self):
        """Open tile in new window"""
        self.ensure_one()

        if not self.embed_url:
            raise UserError(_("No embed URL available for this tile."))

        return {
            "type": "ir.actions.act_url",
            "url": self.embed_url,
            "target": "new",
        }

    def action_link_report(self):
        """Link tile to an existing report"""
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Link Report"),
            "res_model": "powerbi.tile.link.wizard",
            "view_mode": "form",
            "context": {"default_tile_id": self.id},
            "target": "new",
        }

    def action_refresh_tile(self):
        """Refresh tile data"""
        self.ensure_one()

        if not self.dataset_id:
            raise UserError(_("No dataset associated with this tile."))

        # Trigger dataset refresh
        self.dataset_id.action_refresh_dataset()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Refreshing"),
                "message": _("Tile data refresh initiated!"),
                "type": "info",
                "sticky": False,
            },
        }


class PowerBIDashboardViewer(models.TransientModel):
    _name = "powerbi.dashboard.viewer"
    _description = "Power BI Dashboard Viewer"

    dashboard_id = fields.Many2one("powerbi.dashboard", string="Dashboard")
    embed_url = fields.Char(string="Embed URL")
    web_url = fields.Char(string="Web URL")
    dashboard_name = fields.Char(string="Dashboard Name")
