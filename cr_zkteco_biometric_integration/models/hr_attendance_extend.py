# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields


class HrAttendance(models.Model):
    """
    Extends hr.attendance to store biometric-specific calculations
    like Late Arrival and Early Leaving.
    """

    _inherit = "hr.attendance"

    is_late = fields.Boolean(
        string="Late Arrival",
        default=False,
        help="Flag indicating if the employee checked in after the shift start time (plus grace).",
    )
    late_minutes = fields.Float(
        string="Late Minutes",
        default=0.0,
        help="Number of minutes late relative to shift start.",
    )
    is_early_leaving = fields.Boolean(
        string="Early Leaving",
        default=False,
        help="Flag indicating if the employee checked out before the shift end time (minus grace).",
    )
    early_leaving_minutes = fields.Float(
        string="Early Leaving Minutes",
        default=0.0,
        help="Number of minutes the employee left before their shift ended.",
    )
