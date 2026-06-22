# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    x_line_category = fields.Char(string='x_line_category')
