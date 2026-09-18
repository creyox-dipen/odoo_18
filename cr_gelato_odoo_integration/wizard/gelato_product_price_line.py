# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)

class GelatoProductPriceLine(models.TransientModel):
    _name = 'gelato.product.price.line'
    _description = 'Gelato Product Price Line'

    wizard_id = fields.Many2one('gelato.product.price.wizard', string='Wizard')
    country = fields.Char()
    quantity = fields.Integer()
    price = fields.Float()
    currency = fields.Char()
    page_count = fields.Float()
