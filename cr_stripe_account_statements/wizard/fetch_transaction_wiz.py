from datetime import datetime, time
from odoo import models, fields, api
from datetime import date, datetime, timedelta
from odoo.exceptions import UserError, ValidationError

class FetchTransactionWiz(models.TransientModel):
    _name = "fetch.transaction.wiz"
    _description = "Fetches the Transactions for the given range of dates"

    from_date = fields.Date(string="From", required=True)
    to_date = fields.Date(string="To", required=True)

    def action_fetch_transaction(self):
        """
        This method fetches the transactions from stripe in between the given date range
        """
        print("Fetching Transactions...")

        # Validate dates
        if self.from_date > self.to_date:
            raise UserError("'From' date must be earlier than or equal to 'To' date.")

        # Ensure provider exists
        provider = self.env['payment.provider'].search(
            [('code', '=', 'stripe'), ('state', '!=', 'disabled')],
            limit=1)
        if not provider:
            raise UserError('The Stripe payment provider is not configured or disabled.')

        from_timestamp = int(datetime.combine(self.from_date, time.min).timestamp())
        to_timestamp = int(datetime.combine(self.to_date, time.max).timestamp())

        payload = {
            'created[gte]': from_timestamp,
            'created[lte]': to_timestamp,
            'limit': 100
        }

        # Make API request
        try:
            response = provider._stripe_make_request('balance_transactions', payload=payload, method='GET')
            tx_list = response.get('data') if isinstance(response, dict) else response
            if tx_list:
                # Find the bank journal - this assumes a journal named 'Stripe' exists.
                stripe_journal = self.env['account.journal'].search([('name', '=', 'Stripe')], limit=1)
                if not stripe_journal:
                    raise UserError("Please configure a bank journal named 'Stripe'.")
                # Use the helper defined on account.journal
                stripe_journal._create_bank_statements_from_transactions(stripe_journal, tx_list)
                return {'type': 'ir.actions.act_window_close'}
        except Exception as e:
            raise UserError(f"Stripe API request failed: {str(e)}")

    # def create_bank_statements(self, response):
    #     # Find bank account from the journal
    #     stripe_journal = self.env['account.journal'].search([('name', '=', 'Stripe')], limit=1)
    #     if not stripe_journal:
    #         raise UserError("Please configure a bank journal named 'Stripe'.")
    #
    #     for tx in response.get('data'):
    #
    #         # payment received
    #         if tx.get('type') == 'charge':
    #             print("Payment Transaction")
    #
    #         elif tx.get('type') == 'refund':
    #             print("Refund Payment")
    #
    #         else:
    #             print("other : ",tx.get('type'))
