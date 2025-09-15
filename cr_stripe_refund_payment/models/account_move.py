# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields
import logging
log = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_stripe_refund_invoice(self):
        log.info("➡️➡️➡️ Refund is initiating...")

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'payment.refund.wiz',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_id': self.id }
        }
