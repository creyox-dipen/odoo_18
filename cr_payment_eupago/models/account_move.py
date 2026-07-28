# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.addons.cr_payment_eupago import const

class AccountMove(models.Model):
    _inherit = "account.move"

    can_eupago_refund = fields.Boolean(
        string="Can Refund via euPago",
        compute="_compute_can_eupago_refund",
    )

    def _compute_can_eupago_refund(self):
        for move in self:
            if move.state == "posted" and move.payment_state in ("paid", "in_payment", "partial"):
                # Find if there is a successful euPago Credit Card or MB WAY transaction linked to this invoice
                # Transactions are linked via the invoice's transaction_ids field (standard payment integration)
                has_refundable_tx = any(
                    tx.provider_code in (const.PROVIDER_CODE_CC, const.PROVIDER_CODE_MBWAY) and tx.state == "done"
                    for tx in move.transaction_ids
                )
                move.can_eupago_refund = has_refundable_tx
            else:
                move.can_eupago_refund = False

    def action_eupago_refund(self):
        self.ensure_one()
        
        if not self.can_eupago_refund:
            raise UserError(_("This invoice cannot be refunded via euPago API. Only invoices paid via euPago Credit Card or MB WAY can be automatically refunded."))

        # Find the valid euPago transaction
        refundable_tx = self.transaction_ids.filtered(
            lambda tx: tx.provider_code in (const.PROVIDER_CODE_CC, const.PROVIDER_CODE_MBWAY) and tx.state == "done"
        )
        if not refundable_tx:
            raise UserError(_("No valid euPago Credit Card or MB WAY transaction found for this invoice."))
        
        # In case of multiple transactions (e.g. retries), get the latest one
        refundable_tx = refundable_tx.sorted(key=lambda t: t.id, reverse=True)[0]

        return {
            "name": _("euPago Refund"),
            "type": "ir.actions.act_window",
            "res_model": "cr.eupago.refund.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_move_id": self.id,
                "default_transaction_id": refundable_tx.id,
                "default_amount_to_refund": self.amount_total,
            },
        }
