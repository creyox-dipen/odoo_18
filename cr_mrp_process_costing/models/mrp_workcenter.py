# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import api, fields, models

class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    overhead_cost_per_hour = fields.Float(string="Hourly Overhead Price")
    labour_cost_per_hour = fields.Float(string="Hourly Labour Price")