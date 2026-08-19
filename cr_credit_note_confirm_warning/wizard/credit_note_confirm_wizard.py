# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import fields, models

class CreditNoteConfirmWizard(models.TransientModel):
    _name = 'credit.note.confirm.wizard'
    _description = 'Credit Note Confirm Wizard'

    move_ids = fields.Many2many(
        comodel_name='account.move',
        string="Credit Notes",
    )

    def action_confirm(self):
        """Proceeds with the standard confirmation process and posts the Credit Note."""
        if self.move_ids:
            return self.move_ids.with_context(skip_credit_note_warning=True).action_post()
