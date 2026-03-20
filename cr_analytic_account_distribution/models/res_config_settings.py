# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import fields, api, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    analytic_account_setting = fields.Selection(
        selection=[
            ("analytic_account", "Analytic Account"),
            ("analytic_distribution", "Analytic Distribution"),
        ],
        string="Analytic Entry Type",
        config_parameter="cr_analytic_account.analytic_account_setting",
    )
