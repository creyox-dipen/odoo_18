# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api

class SaleSubscriptionPlan(models.Model):
    _inherit = "sale.subscription.plan"
    _description = "Add option to create draft invoice"

    is_draft = fields.Boolean(string='Draft Invoice', help="if selected invoice draft will generated instead of directly posted")