# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields

class SaleSubscriptionPlan(models.Model):
    _inherit = "sale.subscription.plan"
    _description = "Add option to create draft invoice"

    is_draft = fields.Boolean(string='Draft Invoice')

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _process_auto_invoice(self, invoice):
        if self.plan_id.is_draft:
            return
        return super()._process_auto_invoice(invoice)