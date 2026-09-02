# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields


class ManufacturingPartNumber(models.Model):
    _name = "manufacturing.part.number"
    _description = "Manufacturing Part Number"

    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
    )
