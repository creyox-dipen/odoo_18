# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_pay_with_ach(self):
        self.ensure_one()

        provider = self.env['payment.provider'].search(
            [('code', '=', 'stripe'), ('company_id', '=', self.company_id.id), ('state', '!=', 'disabled')], limit=1)
        if not provider:
            raise UserError('The Stripe payment provider is not configured or disabled.')
        ach_method = self.env['payment.method'].search([('code', '=', 'ach_direct_debit')], limit=1)
        if not ach_method:
            raise UserError('The ACH payment method is not available.')
        if ach_method.id not in provider.payment_method_ids.ids:
            raise UserError('The Stripe provider does not support ACH.')
        if self.currency_id.name != 'USD':
            raise UserError('ACH payments are only available in USD.')

        # let user repayment if payment not done yet
        tx = self.env['payment.transaction'].search([
            ('invoice_ids', 'in', self.ids),
            ('provider_id', '=', provider.id),
        ], limit=1, order="id desc")

        if tx and tx.state in ['done']:
            raise UserError("This invoice is already paid.")

        if tx and tx.state in ['draft', 'pending', 'in_process']:
            # Option 1: Reuse the existing transaction
            tx.write({
                'reference': f'INV-{self.id}',
                'amount': self.amount_residual,
                'currency_id': self.currency_id.id,
                'partner_id': self.partner_id.id,
            })
            tx._set_pending()
        else:
            # Option 2: Create a new transaction
            tx_vals = {
                'provider_id': provider.id,
                'payment_method_id': ach_method.id,
                'reference': f'INV-{self.id}',
                'amount': self.amount_residual,
                'currency_id': self.currency_id.id,
                'partner_id': self.partner_id.id,
                'invoice_ids': [(6, 0, [self.id])],
                'state': 'draft',
            }
            tx = self.env['payment.transaction'].create(tx_vals)
            tx._set_pending()


        # This reads Odoo’s configured website base URL (the domain + optional port + scheme), e.g.https://company.example.com or http://localhost:8069.
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        # generates the customer portal link for this invoice. Example: "/my/invoices/1234?access_token=abcd1234".
        portal_url = self.get_portal_url()
        success_url = base_url + portal_url
        cancel_url = base_url + portal_url
        unit_amount = int(self.amount_residual * (10 ** self.currency_id.decimal_places))
        payload = {
            'client_reference_id': tx.reference,
            'mode': 'payment',
            # Stripe requires indexed array notation for list fields:
            'payment_method_types[0]': 'us_bank_account',
            # First line item (quantity and price_data fields)
            'line_items[0][quantity]': 1,
            'line_items[0][price_data][currency]': 'usd',
            'line_items[0][price_data][unit_amount]': unit_amount,
            'line_items[0][price_data][product_data][name]': f"Payment for {self.name}",
            'success_url': success_url,
            'cancel_url': cancel_url,
            # Flatten metadata as well:
            # 'metadata[reference]': tx.reference,  # <--- ensures webhook can map it back
            # 'metadata[tx_id]': str(tx.id),
            # 'metadata[invoice_id]': str(self.id),
            'payment_intent_data[metadata][reference]': tx.reference,
            'payment_intent_data[metadata][tx_id]': str(tx.id),
            'payment_intent_data[metadata][invoice_id]': str(self.id),
            'payment_intent_data[description]': tx.reference,
        }
        if self.partner_id.email:
            payload['customer_email'] = self.partner_id.email

        session = provider._stripe_make_request('checkout/sessions', payload=payload, method='POST')
        if 'error' in session:
            raise UserError(session['error'].get('message', 'An error occurred while creating the checkout session.'))
        payment_intent_id = session.get('payment_intent')
        if payment_intent_id:
            tx.provider_reference = payment_intent_id
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': session['url'],
        }