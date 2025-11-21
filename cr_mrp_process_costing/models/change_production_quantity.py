# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, api

class ChangeProductionQty(models.TransientModel):
    _inherit = 'change.production.qty'

    def change_prod_qty(self):
        res = super().change_prod_qty()

        self.mo_id.labour_costing_ids.lab_planned_hour *= self.product_qty
        self.mo_id.labour_costing_ids.lab_actual_hour *= self.product_qty

        return res
