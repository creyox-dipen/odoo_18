# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields, api, _

class ChannableShippingMapping(models.Model):
    _name = 'channable.shipping.mapping'
    _description = 'Channable Shipping Mapping'
    _order = 'id'

    marketplace_id = fields.Many2one(
        'channable.marketplace', string='Marketplace',
        required=True, ondelete='cascade'
    )
    channable_shipping_method = fields.Char(
        string='Channable Shipping Method', required=True,
        help='The shipping method name from the Channable API payload, e.g. DHL Express, Standard Delivery'
    )
    carrier_id = fields.Many2one(
        'delivery.carrier', string='Odoo Carrier',
        required=True, help='Link to your Odoo delivery/carrier method'
    )

    _sql_constraints = [
        ('uniq_shipping_method_marketplace', 'unique(marketplace_id, channable_shipping_method)', 
         'This Channable shipping method name is already mapped for this marketplace!')
    ]
