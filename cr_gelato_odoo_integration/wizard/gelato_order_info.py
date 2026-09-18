# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class GelatoOrderWizard(models.TransientModel):
    _name = 'gelato.order.wizard'
    _description = 'Gelato Order Info'

    order_id = fields.Char('Order ID')
    customer_reference_id = fields.Char('Customer Reference ID')
    fulfillment_status = fields.Char('Fulfillment Status')
    financial_status = fields.Char('Financial Status')
    currency = fields.Char('Currency')
    channel = fields.Char('Channel')
    store_id = fields.Char('Store ID')
    created_at = fields.Datetime('Created At')
    updated_at = fields.Datetime('Updated At')
    ordered_at = fields.Datetime('Ordered At')

    items_json = fields.Text('Items')
    shipment_json = fields.Text('Shipment')
    billing_json = fields.Text('Billing Entity')
    shipping_json = fields.Text('Shipping Address')
    return_json = fields.Text('Return Address')
    receipts_json = fields.Text('Receipts')

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'order_date' in fields_list:
            res['order_date'] = fields.Datetime.from_string('2025-04-22 07:45:16')
        return res
