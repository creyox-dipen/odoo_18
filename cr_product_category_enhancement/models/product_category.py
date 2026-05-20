# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, api, _
from odoo.osv import expression
from odoo.exceptions import UserError


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

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("restrict_categ_evr"):
            for vals in vals_list:
                if vals.get("name") not in ["EVR", "Bank Hours"]:
                    raise UserError(
                        _(
                            "You should only create for this process the products of evr or bank hour category"
                        )
                    )
        return super(ProductCategory, self).create(vals_list)
