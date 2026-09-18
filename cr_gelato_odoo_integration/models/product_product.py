# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import fields, models, api
import logging

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    cr_product_uid = fields.Char(name="Product UID of Gelato", readonly=True)
    lst_price = fields.Float(
        compute="_compute_cr_lst_price",
        inverse="_inverse_cr_product_lst_price",
    )
    list_price = fields.Float(
        compute="_compute_cr_list_price",
        store=True
    )
    cr_fix_price = fields.Float()

    def action_get_gelato_product_info(self):
        wizard = self.env['gelato.product.template.wizard'].create({
            'product_uid': self.cr_product_uid,  # assuming you have 'product_uid' in your template
        })

        # Fetch product details from the Gelato API
        wizard.fetch_product_details()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'gelato.product.template.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def open_gelato_price_wizard(self):
        product_uid = self.cr_product_uid

        wizard = self.env['gelato.product.price.wizard'].create({
            'product_uid': product_uid,
        })

        wizard.fetch_product_prices(product_uid)

        return {
            'name': 'Gelato Product Price Wizard',
            'type': 'ir.actions.act_window',
            'res_model': 'gelato.product.price.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def _inverse_cr_product_lst_price(self):
        Uom = self.env['uom.uom']

        for product in self:
            if self.env.context.get("uom"):
                target_uom = Uom.browse(self.env.context["uom"])
                cr_fix_price = product.uom_id._compute_price(product.lst_price, target_uom)
            else:
                cr_fix_price = product.lst_price

            product.cr_fix_price = cr_fix_price

            template = product.product_tmpl_id

            if template.product_variant_count == 1:
                template.list_price = cr_fix_price
            else:
                other_variants = template.product_variant_ids - product
                all_prices = other_variants.mapped("cr_fix_price") + [product.lst_price]
                min_price = min(all_prices)
                template.with_context(skip_update_fix_price=True).list_price = min_price

    def _compute_product_price_extra(self):
        for data in self:
            data.price_extra = 0.0

    @api.depends("cr_fix_price")
    def _compute_cr_lst_price(self):
        uom_uom = self.env["uom.uom"]
        for data in self:
            cr_price = data.cr_fix_price or data.list_price
            if self.env.context.get("uom"):
                ref_uom = uom_uom.browse(self.env.context["uom"])
                cr_price = data.uom_id._compute_price(cr_price, ref_uom)
            else:
                _logger.debug("Computed lst_price without UoM: %s", cr_price)

            data.lst_price = cr_price

    def _compute_cr_list_price(self):
        uom_uom = self.env["uom.uom"]
        for data in self:
            cr_price = data.cr_fix_price or data.product_tmpl_id.list_price
            if self.env.context.get("uom"):
                ref_uom = uom_uom.browse(self.env.context["uom"])
                cr_price = data.uom_id._compute_price(cr_price, ref_uom)
            else:
                _logger.debug("Computed list_price without UoM: %s", cr_price)

            data.list_price = cr_price

