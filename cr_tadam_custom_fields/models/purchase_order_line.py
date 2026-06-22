# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    x_line_category = fields.Selection([
        ('service', 'SERVICE'),
        ('refund', 'REFUND'),
    ], string='x_line_category')
