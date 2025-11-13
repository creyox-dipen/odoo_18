# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields

class StockPicking(models.Model):
    _inherit = "stock.picking"

    analytic_account_manage = fields.Selection(
        selection=[('move','By Stock Move'), ('picking', 'By Picking'), ('none', 'Not Applicable')],
        string='Apply Analytic Accounting by : Picking or Move?',
    )