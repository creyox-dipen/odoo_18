# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)


class BiometricAttendanceAlertLog(models.Model):
    """
    Tracks sent attendance alerts to prevent duplicate emails.
    """

    _name = "biometric.attendance.alert.log"
    _description = "Biometric Attendance Alert Log"

    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Employee",
        required=True,
        ondelete="cascade",
    )
    alert_date = fields.Date(
        string="Alert Date",
        required=True,
        index=True,
    )
    alert_type = fields.Selection(
        selection=[
            ("absent", "Absent Alert"),
        ],
        string="Alert Type",
        default="absent",
        required=True,
    )
