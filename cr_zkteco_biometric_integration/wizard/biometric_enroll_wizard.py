# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BiometricEnrollWizard(models.TransientModel):
    _name = "biometric.enroll.wizard"
    _description = "Biometric Enrollment Wizard"

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    device_id = fields.Many2one(
        "biometric.device",
        string="Biometric Device",
        required=True,
        domain=[("active", "=", True)],
    )
    enroll_type = fields.Selection(
        [("finger", "Fingerprint"), ("face", "Face")],
        string="Enrollment Type",
        default="finger",
        required=True,
    )

    finger_index = fields.Selection(
        [
            ("0", "Left Little"),
            ("1", "Left Ring"),
            ("2", "Left Middle"),
            ("3", "Left Index"),
            ("4", "Left Thumb"),
            ("5", "Right Thumb"),
            ("6", "Right Index"),
            ("7", "Right Middle"),
            ("8", "Right Ring"),
            ("9", "Right Little"),
        ],
        string="Finger",
        default="5",
        help="Select which finger to enroll.",
    )

    def action_start_enrollment(self):
        self.ensure_one()
        if not self.employee_id.device_user_id:
            raise UserError(
                _("Please set a Biometric User ID for this employee first.")
            )

        command_text = ""
        if self.enroll_type == "finger":
            # Format: ENROLL_FP PIN={pin} FID={index}
            # Note: FID is 0-9
            command_text = f"ENROLL_FP PIN={self.employee_id.device_user_id}\tFID={self.finger_index}"
        elif self.enroll_type == "face":
            # Note: 111 is the universal index for Face enrollment on most ZKTeco ADMS devices
            command_text = f"ENROLL_FP PIN={self.employee_id.device_user_id}\tFID=111"

        if command_text:
            self.env["biometric.device.command"].sudo().create(
                {
                    "device_id": self.device_id.id,
                    "command_text": command_text,
                }
            )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Command Sent"),
                    "message": _(
                        "The machine has been notified. Please place the employee's %s on the device."
                    )
                    % (self.enroll_type == "finger" and "finger" or "face"),
                    "sticky": False,
                },
            }
