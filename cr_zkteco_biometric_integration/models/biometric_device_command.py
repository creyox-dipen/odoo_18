# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api


class BiometricDeviceCommand(models.Model):
    """
    Stores commands to be sent to the biometric device via ADMS.
    The device pulls these commands during its heartbeat (getrequest).
    """

    _name = "biometric.device.command"
    _description = "Biometric Device Command"
    _order = "create_date desc"

    device_id = fields.Many2one(
        comodel_name="biometric.device",
        string="Device",
        required=True,
        ondelete="cascade",
    )
    command_text = fields.Char(
        string="Command Text",
        required=True,
        help="The actual command string sent to the device (e.g., REBOOT, CLEAR LOG).",
    )
    status = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("success", "Success"),
            ("failed", "Failed"),
        ],
        default="pending",
        string="Status",
        index=True,
    )
    response_text = fields.Text(
        string="Device Response",
        readonly=True,
    )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.device_id.name}: {rec.command_text}"

    @api.model
    def _gc_commands(self):
        """
        Garbage Collection for commands.
        Removes ALL successful/failed commands to keep the history clean.
        This runs according to the interval set in the Scheduled Action.
        """
        processed_commands = self.search([("status", "in", ["success", "failed"])])
        if processed_commands:
            processed_commands.unlink()
