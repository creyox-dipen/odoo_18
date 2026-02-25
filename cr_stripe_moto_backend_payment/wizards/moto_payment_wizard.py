# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError
import stripe
# from stripe.error import StripeError
import logging

_logger = logging.getLogger(__name__)

class MotoPaymentWizard(models.TransientModel):
    _name = "moto.payment.wizard"
    _description = "Wizard to enter card details"

    partner_id = fields.Many2one(string="Partner", comodel_name="res.partner")
    name_on_card = fields.Char(string="Name on Card")
    address = fields.Char(string="Address Line")
    postcode = fields.Integer(string="Postcode")
    mobile_no = fields.Integer(string="Mobile")
    email = fields.Char(string="Email")
    currency_id = fields.Many2one(comodel_name="res.currency", default=lambda self: self.env.company.currency_id.id)
    amount = fields.Monetary(string="Amount", currency_field="currency_id")
    description = fields.Char(string="Description")
    is_manual_override = fields.Boolean(string="Manual Override")
    card_no = fields.Integer(string="Card Number")
    expiry_date = fields.Date(string="Expiry Date")
    cvc = fields.Integer(string="CVC")
    is_save_card = fields.Boolean(string="Save Card Details")

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            move = self.env['account.move'].browse(active_id)
            if move.partner_id:
                defaults['partner_id'] = move.partner_id.id
            if 'amount' in fields_list:
                defaults['amount'] = move.amount_residual
            if 'currency_id' in fields_list:
                defaults['currency_id'] = move.currency_id.id
            if 'description' in fields_list:
                defaults['description'] = move.name
        return defaults

    # def process_moto_payment(self):
    #     active_id = self.env.context.get('active_id')
    #     if not active_id:
    #         raise UserError("No invoice selected.")
    #     move = self.env['account.move'].browse(active_id)
    #     if move.move_type != 'out_invoice' or move.state != 'posted' or move.payment_state == 'paid':
    #         raise UserError("Invalid invoice for payment.")
    #     partner = self.partner_id or move.partner_id
    #     if not partner:
    #         raise UserError("No partner found.")
    #     if not self.card_no or not self.expiry_date or not self.cvc:
    #         raise ValidationError("Card details are required.")
    #     if self.amount <= 0:
    #         raise ValidationError("Amount must be positive.")
    #     providers = self.env['payment.provider'].search([('code', '=', 'stripe'), ('state', '=', 'enabled')], limit=1)
    #     if not providers:
    #         raise UserError("No enabled Stripe provider found.")
    #     provider = providers
    #     # Set Stripe API key based on mode
    #     stripe_keys = provider._stripe_get_api_keys(move.company_id)
    #     stripe.api_key = stripe_keys['secret_key']
    #     # Prepare payment data
    #     amount = self.amount or move.amount_residual
    #     currency = self.currency_id or move.currency_id
    #     amount_cents = int(amount * 100)  # Assuming 2 decimal places
    #     exp_month = self.expiry_date.month
    #     exp_year = self.expiry_date.year
    #     billing_details = {}
    #     if self.name_on_card:
    #         billing_details['name'] = self.name_on_card
    #     if self.email:
    #         billing_details['email'] = self.email
    #     if self.mobile_no:
    #         billing_details['phone'] = str(self.mobile_no)
    #     address_details = {}
    #     if self.address:
    #         address_details['line1'] = self.address
    #     if self.postcode:
    #         address_details['postal_code'] = str(self.postcode)
    #     if address_details:
    #         billing_details['address'] = address_details
    #     card_data = {
    #         'number': str(self.card_no),
    #         'exp_month': exp_month,
    #         'exp_year': exp_year,
    #         'cvc': str(self.cvc),
    #     }
    #     payment_method_data = {
    #         'type': 'card',
    #         'card': card_data,
    #         'billing_details': billing_details,
    #     }
    #     payment_method_options = {
    #         'card': {'moto': True},
    #     }
    #     kwargs = {
    #         'amount': amount_cents,
    #         'currency': currency.name.lower(),
    #         'payment_method_data': payment_method_data,
    #         'confirm': True,
    #         'payment_method_options': payment_method_options,
    #         'description': self.description or f"Payment for {move.name}",
    #         'metadata': {
    #             'odoo_invoice_id': str(move.id),
    #             'odoo_partner_id': str(partner.id),
    #         },
    #     }
    #     if self.is_save_card:
    #         kwargs['setup_future_usage'] = 'off_session'
    #     if self.is_manual_override:
    #         kwargs['capture_method'] = 'manual'
    #     try:
    #         payment_intent = stripe.PaymentIntent.create(**kwargs)
    #     except StripeError as e:
    #         _logger.error("Stripe error during MOTO payment: %s", e)
    #         raise UserError(f"Payment processing failed: {e.user_message or str(e)}")
    #     if payment_intent.status != 'succeeded':
    #         raise UserError(f"Payment not successful. Status: {payment_intent.status}")
    #     # Handle saved card if requested
    #     payment_method_id = payment_intent.payment_method
    #     token = False
    #     if self.is_save_card and payment_method_id:
    #         card = stripe.PaymentMethod.retrieve(payment_method_id).card
    #         token_vals = {
    #             'name': f"Card ending {card.last4}",
    #             'partner_id': partner.id,
    #             'provider_id': provider.id,
    #             'acquirer_reference': payment_method_id,
    #             'verified': True,
    #         }
    #         token = self.env['payment.token'].create(token_vals)
    #     # Create transaction record
    #     tx_vals = {
    #         'provider_id': provider.id,
    #         'amount': amount,
    #         'currency_id': currency.id,
    #         'partner_id': partner.id,
    #         'operation': 'online_direct',
    #         'reference': move.name,
    #         'state': 'done',
    #         'state_message': payment_intent.id,
    #         'acquirer_reference': payment_intent.id,
    #         'payment_method_id': token.id if token else False,
    #     }
    #     tx = self.env['payment.transaction'].create(tx_vals)
    #     # Create and post payment
    #     journal = move.journal_id
    #     payment_method_line_id = journal.inbound_payment_method_line_ids.filtered(
    #         lambda line: line.payment_method_id.code == 'manual'
    #     )[:1]
    #     payment_vals = {
    #         'name': move.name,
    #         'payment_type': 'inbound',
    #         'partner_type': 'customer',
    #         'partner_id': partner.id,
    #         'amount': amount,
    #         'currency_id': currency.id,
    #         'date': fields.Date.context_today(self),
    #         'journal_id': journal.id,
    #         'ref': self.description or f"MOTO Payment for {move.name}",
    #         'payment_method_line_id': payment_method_line_id.id if payment_method_line_id else False,
    #         'invoice_ids': [(4, move.id)],
    #         'payment_transaction_id': tx.id,
    #     }
    #     payment = self.env['account.payment'].create(payment_vals)
    #     payment.action_post()
    #     return {'type': 'ir.actions.act_window_close'}