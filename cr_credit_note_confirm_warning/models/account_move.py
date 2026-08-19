# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models

class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        """Override action_post to show wizard for credit notes."""
        if not self._context.get('skip_credit_note_warning'):
            for move in self:
                if move.move_type in ('out_refund', 'in_refund'):
                    return {
                        'name': 'Warning / Note',
                        'type': 'ir.actions.act_window',
                        'res_model': 'credit.note.confirm.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {'default_move_ids': self.ids},
                    }
        return super().action_post()
