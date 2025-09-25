# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api
from datetime import date
from odoo.exceptions import UserError

class AccountJournal(models.Model):
    _inherit = "account.journal"

    def action_fetch_transactions(self):
        print("fetching transactions...")
        print(self)
        for journal in self:
            provider = self.env['payment.provider'].search(
                [('code', '=', 'stripe'), ('company_id', '=', self.company_id.id), ('state', '!=', 'disabled')],
                limit=1)
            if not provider:
                raise UserError('The Stripe payment provider is not configured or disabled.')

            payload = {}

            transactions = provider._stripe_make_request('balance_transactions', payload=payload, method='GET')

            print("Transactions : ", transactions)

            for tx in transactions.get('data',[]):
                print(tx)