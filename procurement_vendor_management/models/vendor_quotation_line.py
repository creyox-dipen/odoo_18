# -*- coding: utf-8 -*-
from odoo import models, fields, api

class VendorQuotationLine(models.Model):
    _name = 'vendor.quotation.line'
    _description = 'Vendor Quotation Line'

    quotation_id = fields.Many2one('vendor.quotation', string="Quotation", required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Product", required=True)
    quantity = fields.Float(string="Quantity", required=True, default=1.0)
    
    currency_id = fields.Many2one('res.currency', related='quotation_id.currency_id', string='Currency', readonly=True, store=True)
    price_unit = fields.Monetary(string="Unit Price", required=True, currency_field='currency_id')
    subtotal = fields.Monetary(string="Subtotal", compute="_compute_subtotal", currency_field='currency_id', store=True)

    product_name = fields.Char(string="Product Name", compute="_compute_product_name", store=True)

    @api.depends('product_id')
    def _compute_product_name(self):
        for line in self:
            line.product_name = line.product_id.display_name or line.product_id.name

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit
