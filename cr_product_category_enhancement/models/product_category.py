# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, api
from odoo.osv import expression


class ProductCategory(models.Model):
    _inherit = "product.category"

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        if self.env.context.get("restrict_categ_evr"):
            domain = expression.AND(
                [domain or [], [("name", "in", ["EVR", "Bank Hours"])]]
            )
        return super(ProductCategory, self)._search(
            domain, offset=offset, limit=limit, order=order
        )
