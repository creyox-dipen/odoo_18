# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import datetime, timedelta
import json

_logger = logging.getLogger(__name__)


class PowerBIPipeline(models.Model):
    _name = "powerbi.pipeline"
    _description = "Power BI Data Pipeline"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "sequence, id"

    stage_kanban_json = fields.Text(compute="_compute_stage_kanban_json")

    @api.depends("stage_ids.name", "stage_ids.sequence")
    def _compute_stage_kanban_json(self):
        for rec in self:
            stages = []
            for stage in rec.stage_ids.sorted("sequence"):
                stages.append(
                    {
                        "name": stage.name,
                    }
                )
            rec.stage_kanban_json = json.dumps(stages)

    # Basic Information
    name = fields.Char(string="Pipeline Name", required=True, tracking=True)
    sequence = fields.Integer(string="Sequence", default=10)
    description = fields.Text(string="Description")

    # Relations
    pipeline_id = fields.Char(string="Pipeline ID")
    config_id = fields.Many2one(
        "powerbi.config", string="Configuration", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one(
        "res.company", string="Company", related="config_id.company_id", store=True
    )

    dataset_ids = fields.Many2many(
        "powerbi.dataset",
        string="Datasets to Refresh",
        help="Datasets that will be refreshed after data ingestion",
    )

    # Scheduling
    schedule = fields.Selection(
        [
            ("manual", "Manual"),
            ("hourly", "Hourly"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
        ],
        string="Schedule",
        default="manual",
        tracking=True,
    )

    next_run_date = fields.Datetime(string="Next Run Date", readonly=True)
    last_run_date = fields.Datetime(string="Last Run Date", readonly=True)

    # State
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("paused", "Paused"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    # Pipeline Settings
    auto_retry = fields.Boolean(string="Auto Retry on Failure", default=True)
    max_retry_attempts = fields.Integer(string="Max Retry Attempts", default=3)
    notify_on_completion = fields.Boolean(string="Notify on Completion", default=True)
    notify_on_failure = fields.Boolean(string="Notify on Failure", default=True)
    notification_user_ids = fields.Many2many(
        "res.users", "pipeline_notification_users_rel", string="Notification Recipients"
    )

    # Stages
    stage_ids = fields.One2many(
        "powerbi.pipeline.stage", "pipeline_id", string="Pipeline Stages"
    )
    stage_count = fields.Integer(
        string="Stages", compute="_compute_stage_count", store=True
    )

    @api.depends("stage_ids")
    def _compute_stage_count(self):
        for record in self:
            record.stage_count = len(record.stage_ids)

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-create default 5 stages when pipeline is created"""
        pipelines = super(PowerBIPipeline, self).create(vals_list)
        for pipeline in pipelines:
            pipeline._create_default_stages()
        return pipelines

    def _create_default_stages(self):
        """Create the 5 default pipeline stages"""
        self.ensure_one()

        stage_model = self.env["powerbi.pipeline.stage"]

        default_stages = [
            {"name": "Development", "sequence": 10, "pipeline_id": self.id},
            {"name": "Test", "sequence": 20, "pipeline_id": self.id},
            {"name": "Production", "sequence": 30, "pipeline_id": self.id},
        ]

        for stage_vals in default_stages:
            stage_model.create(stage_vals)

    def action_view_stages(self):
        """View pipeline stages"""
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Pipeline Stages"),
            "res_model": "powerbi.pipeline.stage",
            "view_mode": "list,form",
            "domain": [("pipeline_id", "=", self.id)],
            "context": {"default_pipeline_id": self.id},
            "target": "current",
        }

    def _send_notification(self, subject, message, notification_type="info"):
        """Send notification to users"""
        self.ensure_one()

        if not self.notification_user_ids:
            return

        # Create activity for each user
        for user in self.notification_user_ids:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=user.id,
                summary=subject,
                note=message,
            )

        # Also post message to chatter
        self.message_post(
            body=message,
            subject=subject,
            message_type="notification",
            subtype_xmlid="mail.mt_comment",
        )
