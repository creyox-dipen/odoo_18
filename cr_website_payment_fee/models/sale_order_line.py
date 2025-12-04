# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import models, fields, api, _


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    payment_fee = fields.Float(string="Payment Fee", store=True)
