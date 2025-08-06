# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api

class StockPicking(models.Model):
    _inherit = ['stock.picking']

    custom_state_id = fields.Many2one(comodel_name='res.country.state', string='State')
    custom_country_id = fields.Many2one(comodel_name='res.country', string='Country')
    custom_street = fields.Char(string='Street')
    custom_street2 = fields.Char(string='Street2')
    custom_zip = fields.Char(string='Zip')
    custom_city = fields.Char(string='City')

    def create(self, vals):
        sale_order = self.env['sale.order'].search([('name', '=', vals.get('origin'))])
        vals.update({
            'custom_zip': sale_order.custom_zip,
            'custom_city': sale_order.custom_city,
            'custom_street': sale_order.custom_street,
            'custom_street2': sale_order.custom_street2,
            'custom_state_id': sale_order.custom_state_id.id,
            'custom_country_id': sale_order.custom_country_id.id,
        })
        return super().create(vals)