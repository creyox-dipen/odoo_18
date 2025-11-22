# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import fields, models

class ResUsers(models.Model):
    _inherit = "res.users"

    enable_daily_attendance_email = fields.Boolean(string="Enable Daily Attendance Email")