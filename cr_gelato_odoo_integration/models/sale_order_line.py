# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.model_create_multi
    def create(self, vals_list):
        ref = super().create(vals_list)
        if ref.order_id:
            ref.order_id._is_mixing_of_gelato_and_non_gelato_products()
        return ref

    def write(self, vals):
        ref = super().write(vals)
        if self.order_id:
            self.order_id._is_mixing_of_gelato_and_non_gelato_products()
        return ref

    def _action_launch_stock_rule(self, **kwargs):
        gelato_lines = self.filtered(lambda l: l.product_id.cr_product_uid)
        super(SaleOrderLine, self - gelato_lines)._action_launch_stock_rule(**kwargs)
