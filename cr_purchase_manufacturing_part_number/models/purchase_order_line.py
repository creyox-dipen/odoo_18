# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    manufacturing_part_number = fields.Many2one(
        related="product_id.manufacturing_part_no",
        string="Manufacturing Part Number",
        readonly=False,
    )
