# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def find_duplicate_data(self):
        return {
            'name': 'Find Duplicate',
            'type': 'ir.actions.act_window',
            'res_model': 'duplicate.wiz',
            'view_mode': 'form',
            'view_id': self.env.ref('cr_merge_duplicate_data_extended.find_duplicate_form_id').id,
            'target': 'new',
            'context': {
                'active_model': 'res.partner',
                'active_ids': self.ids,
            }
        }

    def merge_duplicate_data(self):
        return {
            'name': 'Merge Duplicate Data',
            'type': 'ir.actions.act_window',
            'res_model': 'duplicate.wiz',
            'view_mode': 'form',
            'view_id': self.env.ref('cr_merge_duplicate_data_extended.merge_duplicate_data_form_id').id,
            'target': 'new',
            'context': {
                'active_model': 'res.partner',
                'active_ids': self.ids,
            }
        }