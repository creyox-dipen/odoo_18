# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = "product.template"

    manufacturing_part_no = fields.Many2one(
        comodel_name="manufacturing.part.number",
        string="מק\"ט יצרן",
    )
