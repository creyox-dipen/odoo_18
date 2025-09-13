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
        _logger.info("refund process started...")

        provider = self.env['payment.provider'].search(
            [('code', '=', 'stripe'), ('state', '!=', 'disabled')], limit=1)

        if not provider:
            raise UserError('The Stripe payment provider is not configured or disabled.')

        if self.payment_transaction_id.provider_code != 'stripe':
            raise UserError("Transaction is done by another provider")

        if self.refund_amount <= 0 or self.refund_amount > self.payment_transaction_id.amount:
            raise UserError("Refund amount must be positive and not exceed the original transaction amount.")

        base_amount = self.refund_amount
        amount_cents = payment_utils.to_minor_currency_units(base_amount, self.payment_transaction_id.currency_id)

        payload = {
            'amount': amount_cents,
            'payment_intent': self.payment_transaction_id.provider_reference,
        }

        try:
            response = provider._stripe_make_request('refunds', payload=payload, method='POST')
            if 'error' in response:
                raise UserError(f"Stripe error: {response['error'].get('message', 'Unknown error')}")
            if response.get('status') != 'succeeded':
                raise UserError(f"Stripe refund initiated but not succeeded: {response.get('status')}")

            # Create credit note with explicit 'partner_id' to avoid KeyError
            default_values = {
                'ref': f"{'Partial ' if self.refund_amount != self.payment_transaction_id.amount else ''}Refund of {self.move_id.name} via Stripe ({self.refund_amount})",
                'partner_id': self.move_id.partner_id.id,  # Explicitly set to prevent KeyError
            }

            if self.refund_amount == self.payment_transaction_id.amount:
                # Full refund: Use full reverse
                credit_note = self.move_id._reverse_moves(default_values_list=[default_values])
            else:
                # Partial refund: Create credit note, copy lines, prorate amounts
                credit_note = self.move_id._reverse_moves(default_values_list=[default_values])
                # Prorate: Adjust each line's price_unit by refund ratio
                ratio = self.refund_amount / self.payment_transaction_id.amount
                for line in credit_note.line_ids.filtered(lambda l: l.debit or l.credit):  # Adjust revenue/tax lines
                    if line.price_unit:
                        line.with_context(check_move_validity=False).price_unit *= ratio
                credit_note._compute_amount()  # Recompute totals

            credit_note.action_post()  # Post the credit note

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'message': 'Refund processed successfully and credit note created.', 'type': 'success'}
            }
        except Exception as e:
            _logger.error(f"Stripe refund failed: {str(e)}")
            raise UserError(f"Refund failed: {str(e)}")