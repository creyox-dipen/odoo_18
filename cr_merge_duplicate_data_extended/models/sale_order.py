# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def find_duplicate_data(self):
        return {
            'name': 'Find Duplicate',
            'type': 'ir.actions.act_window',
            'res_model': 'duplicate.wiz',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'sale.order',
                'active_ids': self.ids,
            }
        }
