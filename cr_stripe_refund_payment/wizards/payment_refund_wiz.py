# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api
import logging
from odoo.exceptions import UserError
from odoo.addons.payment import utils as payment_utils

_logger = logging.getLogger(__name__)


class PaymentRefund(models.TransientModel):
    _name = "payment.refund.wiz"
    _description = "This is payment refund wizard for refund stripe button"

    move_id = fields.Many2one(comodel_name="account.move", string="Invoice", readonly=True)
    payment_transaction_id = fields.Many2one(
        string='Payment Transaction',
        comodel_name='payment.transaction',
        domain="[('provider_code', '=', 'stripe'), ('state', '=', 'done'), ('invoice_ids', 'in', move_id)]",
        required=True
    )
    refund_amount = fields.Float(string='Refund Amount')

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        move_id = self.env.context.get('default_move_id')
        if move_id:
            move = self.env['account.move'].browse(move_id)
            transactions = move.transaction_ids.filtered(lambda t: t.provider_code == 'stripe' and t.state == 'done')
            if len(transactions) == 1:
                res['payment_transaction_id'] = transactions.id
                res['refund_amount'] = transactions.amount  # Default to full refund
        return res

    def make_refund_request(self):
        _logger.info("Refund process started...")

        provider = self.env['payment.provider'].search(
            [('code', '=', 'stripe'), ('state', '!=', 'disabled')], limit=1)

        if not provider:
            raise UserError('The Stripe payment provider is not configured or disabled.')

        if self.payment_transaction_id.provider_code != 'stripe':
            raise UserError("This transaction was made using another payment provider.")

        if self.refund_amount <= 0:
            raise UserError("Refund amount must be greater than zero.")

        if self.refund_amount > self.payment_transaction_id.amount:
            raise UserError("Refund amount cannot exceed the original transaction amount.")

        # Extra check: prevent double refund
        if self.move_id.payment_state == 'reversed':
            raise UserError("This invoice is already refunded.")

        base_amount = self.refund_amount
        amount_cents = payment_utils.to_minor_currency_units(base_amount, self.payment_transaction_id.currency_id)

        payload = {
            'amount': amount_cents,
            'payment_intent': self.payment_transaction_id.provider_reference,
            'metadata[move_id]': self.move_id.id,
            'metadata[tx_id]': self.payment_transaction_id.id,
        }

        try:
            response = provider._stripe_make_request('refunds', payload=payload, method='POST')
            _logger.info("Stripe refund response: %s", response)

            if response.get('error'):
                error_msg = response['error'].get('message', 'Unknown error occurred while processing refund.')
                raise UserError(f"Refund failed: {error_msg}")

            status = response.get('status')

            if status == 'succeeded':
                message = f"Refund of {self.refund_amount} processed successfully and credit note created."
            elif status in ('pending', 'requires_action', 'processing'):
                message = "Refund request submitted to Stripe. It is still processing — please check back later."
            else:
                raise UserError(f"Refund could not be processed. Stripe status: {status}")

            # Credit note creation
            default_values = {
                'ref': f"{'Partial ' if self.refund_amount != self.payment_transaction_id.amount else ''}Refund of {self.move_id.name} via Stripe ({self.refund_amount})",
                'partner_id': self.move_id.partner_id.id,
            }

            if self.refund_amount == self.payment_transaction_id.amount:
                credit_note = self.move_id._reverse_moves(default_values_list=[default_values])
            else:
                credit_note = self.move_id._reverse_moves(default_values_list=[default_values])
                ratio = self.refund_amount / self.payment_transaction_id.amount
                for line in credit_note.line_ids.filtered(lambda l: l.debit or l.credit):
                    if line.price_unit:
                        line.with_context(check_move_validity=False).price_unit *= ratio
                credit_note._compute_amount()

            credit_note.action_post()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f"Refund of {self.refund_amount} processed successfully and credit note created.",
                    'type': 'success',
                    'sticky': False,
                    'next': {
                        'type': 'ir.actions.act_window_close'
                    }
                }
            }

        except UserError:
            raise  # Re-raise clean user errors
        except Exception as e:
            _logger.error("Unexpected Stripe refund failure: %s", str(e))
            raise UserError("An unexpected error occurred while processing the refund. Please try again or check logs.")

