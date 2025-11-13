# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import fields, api, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    analytic_account_setting = fields.Selection([('analytic_account','Analytic Account'), ('analytic_distribution', 'Analytic Distribution')])
