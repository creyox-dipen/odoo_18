# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
import requests

_logger = logging.getLogger(__name__)


class PowerBIPipelineStage(models.Model):
    _name = "powerbi.pipeline.stage"
    _description = "Power BI Pipeline Stage"
    _rec_name = "name"
    _order = "sequence, id"

    # Basic Information
    name = fields.Char(string="Stage Name", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    stage_order = fields.Char(string="Stage Order")
    description = fields.Text(string="Description")

    # Relations
    pipeline_id = fields.Many2one(
        "powerbi.pipeline", string="Pipeline", required=True, ondelete="cascade"
    )
    workspace_id = fields.Many2one(
        "powerbi.workspace", string="Workspace", ondelete="set null"
    )  # NEW FIELD

    # Configuration
    configuration = fields.Text(
        string="Configuration (JSON)",
        help="JSON configuration for stage-specific settings",
    )

    def action_assign_workspace_to_stage(self):
        """Assign workspace to this stage in Power BI"""
        self.ensure_one()

        if not self.workspace_id:
            raise UserError(_("Please select a workspace first."))

        if not self.pipeline_id:
            raise UserError(_("Stage must be associated with a pipeline."))

        try:
            # Get pipeline's config
            config = self.pipeline_id.config_id
            token = config._get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Use stage_order field directly
            stage_order = self.stage_order

            # Assign workspace to pipeline stage
            url = f"https://api.powerbi.com/v1.0/myorg/pipelines/{self.pipeline_id.pipeline_id}/stages/{stage_order}/assignWorkspace"

            data = {"workspaceId": self.workspace_id.workspace_id}

            response = requests.post(url, headers=headers, json=data, timeout=30)

            if response.status_code == 200:
                # Update configuration with workspace info
                config_data = {}
                if self.configuration:
                    try:
                        config_data = json.loads(self.configuration)
                    except:
                        pass

                config_data["powerbi_workspace_id"] = self.workspace_id.workspace_id
                config_data["assigned_at"] = fields.Datetime.now().isoformat()
                self.configuration = json.dumps(config_data)

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Success"),
                        "message": _("Workspace assigned to stage successfully!"),
                        "type": "success",
                        "sticky": False,
                    },
                }

            elif response.status_code == 400:
                raise UserError(
                    _(
                        "Bad request. The workspace may already be assigned to another stage or the stage order is invalid."
                    )
                )

            elif response.status_code == 401:
                raise UserError(
                    _("Authentication failed. Please check your Power BI credentials.")
                )

            elif response.status_code == 403:
                raise UserError(
                    _(
                        "Access denied. You may not have permission to modify this pipeline."
                    )
                )

            elif response.status_code == 404:
                raise UserError(
                    _("Pipeline or stage not found. Stage order may be incorrect.")
                )

            else:
                error_msg = f"Failed to assign workspace: {response.status_code} - {response.text}"
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
            _logger.error("Workspace assignment failed: %s", str(e))
            raise UserError(_("Workspace assignment failed: %s") % str(e))

    def action_unassign_workspace_from_stage(self):
        """Unassign workspace from this stage in Power BI"""
        self.ensure_one()

        if not self.workspace_id:
            raise UserError(_("No workspace is currently assigned to this stage."))

        if not self.pipeline_id:
            raise UserError(_("Stage must be associated with a pipeline."))

        try:
            # Get pipeline's config
            config = self.pipeline_id.config_id
            token = config._get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Use stage_order field directly
            stage_order = self.stage_order

            # Unassign workspace from pipeline stage
            url = f"https://api.powerbi.com/v1.0/myorg/pipelines/{self.pipeline_id.pipeline_id}/stages/{stage_order}/unassignWorkspace"

            response = requests.post(url, headers=headers, timeout=30)

            if response.status_code == 200:
                workspace_name = self.workspace_id.workspace_name

                # Clear workspace assignment in Odoo
                self.workspace_id = False

                # Update configuration
                config_data = {}
                if self.configuration:
                    try:
                        config_data = json.loads(self.configuration)
                    except:
                        pass

                if "powerbi_workspace_id" in config_data:
                    del config_data["powerbi_workspace_id"]
                if "assigned_at" in config_data:
                    del config_data["assigned_at"]

                config_data["unassigned_at"] = fields.Datetime.now().isoformat()
                self.configuration = json.dumps(config_data)

                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Success"),
                        "message": _("Workspace unassigned from stage successfully!"),
                        "type": "success",
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
                        "Access denied. You may not have permission to modify this pipeline."
                    )
                )

            elif response.status_code == 404:
                raise UserError(
                    _("Pipeline or stage not found. Stage order may be incorrect.")
                )

            else:
                error_msg = f"Failed to unassign workspace: {response.status_code} - {response.text}"
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
            _logger.error("Workspace unassignment failed: %s", str(e))
            raise UserError(_("Workspace unassignment failed: %s") % str(e))

    def action_toggle_active(self):
        """Toggle stage active status"""
        for record in self:
            record.is_active = not record.is_active

    def action_deploy_to_next_stage(self):
        """Deploy content from this stage to the next stage in Power BI"""
        self.ensure_one()

        if not self.pipeline_id.pipeline_id:
            raise UserError(
                _("Pipeline does not have a Power BI Pipeline ID configured.")
            )
        if not self.stage_order:
            raise UserError(_("Stage order is not configured for this stage."))

        # Find next stage
        all_stages = self.pipeline_id.stage_ids.sorted("sequence")
        stage_list = list(all_stages)
        current_index = next(
            (i for i, s in enumerate(stage_list) if s.id == self.id), None
        )

        if current_index is None or current_index >= len(stage_list) - 1:
            raise UserError(
                _("This is the last stage. There is no next stage to deploy to.")
            )

        next_stage = stage_list[current_index + 1]

        if not next_stage.stage_order:
            raise UserError(
                _('Next stage "%s" does not have a stage order configured.')
                % next_stage.name
            )

        # Setup
        config = self.pipeline_id.config_id
        token = config._get_valid_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        pipeline_pbi_id = self.pipeline_id.pipeline_id
        source_order = int(self.stage_order)
        target_order = int(next_stage.stage_order)

        # Minimal required payload only
        payload = {
            "sourceStageOrder": source_order,
            "targetStageOrder": target_order,
            "options": {
                "allowCreateArtifact": True,
                "allowOverwriteArtifact": True,
            },
        }

        try:
            response = requests.post(
                f"https://api.powerbi.com/v1.0/myorg/pipelines/{pipeline_pbi_id}/deployAll",
                headers=headers,
                json=payload,
                timeout=60,
            )
        except requests.exceptions.Timeout:
            raise UserError(
                _("Request timed out. Please check the Power BI portal for status.")
            )
        except requests.exceptions.ConnectionError:
            raise UserError(
                _(
                    "Could not connect to Power BI. Please check your internet connection."
                )
            )

        if response.status_code in (200, 202):
            self.pipeline_id.message_post(
                body=_("Deployment triggered: <b>%s</b> → <b>%s</b>")
                % (self.name, next_stage.name),
                message_type="notification",
                subtype_xmlid="mail.mt_comment",
            )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Deployment Triggered"),
                    "message": _(
                        'Deploying from "%s" to "%s". Check the Power BI portal for progress.'
                    )
                    % (self.name, next_stage.name),
                    "type": "success",
                    "sticky": False,
                },
            }

        # Handle errors
        try:
            error = response.json().get("error", {})
            msg = error.get("code", response.text)
        except Exception:
            msg = response.text

        raise UserError(
            _("Deployment failed (HTTP %s): %s") % (response.status_code, msg)
        )
