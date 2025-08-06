# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = ['sale.order']

    custom_state_id = fields.Many2one(comodel_name='res.country.state', string='State')
    custom_country_id = fields.Many2one(comodel_name='res.country', string='Country')
    custom_street = fields.Char(string='Street')
    custom_street2 = fields.Char(string='Street2')
    custom_zip = fields.Char(string='Zip')
    custom_city = fields.Char(string='City')

    @api.onchange('partner_id')
    def get_customer_address(self):
        customer = self.partner_id

        self.custom_zip = customer.zip
        self.custom_city = customer.city
        self.custom_street = customer.street
        self.custom_street2 = customer.street2
        self.custom_state_id = customer.state_id.id
        self.custom_country_id = customer.country_id.id

    def _prepare_invoice(self):
        """
        Transferring custom fields to invoice
        """
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        invoice_vals.update({
            'custom_state_id' : self.custom_state_id.id,
            'custom_zip' : self.custom_zip,
            'custom_street' : self.custom_street,
            'custom_street2' : self.custom_street2,
            'custom_country_id' : self.custom_country_id.id,
            'custom_city' : self.custom_city
        })
        return invoice_vals

