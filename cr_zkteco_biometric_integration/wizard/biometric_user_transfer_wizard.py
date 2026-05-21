# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BiometricUserTransferWizard(models.TransientModel):
    _name = "biometric.user.transfer.wizard"
    _description = "Transfer Biometric User to Other Devices"

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    device_user_id = fields.Char(
        related="employee_id.device_user_id", string="Biometric User ID"
    )
    device_ids = fields.Many2many(
        "biometric.device",
        string="Target Devices",
        required=True,
        domain=[("active", "=", True)],
    )

    template_count = fields.Integer(
        compute="_compute_template_count", string="Available Templates"
    )

    @api.depends("employee_id")
    def _compute_template_count(self):
        for record in self:
            record.template_count = len(record.employee_id.biometric_template_ids)

    def action_transfer(self):
        self.ensure_one()
        if not self.employee_id.device_user_id:
            raise UserError(
                _("Please set a Biometric User ID for this employee first.")
            )

        if not self.employee_id.biometric_template_ids:
            raise UserError(
                _("This employee has no saved biometric templates to transfer.")
            )

        # Reusing existing sync logic but only for selected devices
        self.employee_id.action_sync_to_devices(device_ids=self.device_ids.ids)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Transfer Initiated"),
                "message": _(
                    "User and templates are being pushed to %d selected device(s)."
                )
                % len(self.device_ids),
                "sticky": False,
                "type": "success",
            },
        }
