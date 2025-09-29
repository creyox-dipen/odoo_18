# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api
from datetime import datetime, date
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    cron_name = fields.Char(string="Cron",default="Fetch Stripe Transactions",readonly=True)
    is_active_cron = fields.Boolean(string="Cron Active",default=False)
    statement_type = fields.Selection(
        [
            ('daily', 'Daily Statements'),
            ('weekly', 'Weekly Statements'),
            ('monthly', 'Monthly Statements'),
        ],
        string="Stripe Statement Type",
        default='daily',
    )
    next_exe_date = fields.Datetime(string="Next Execution Date", readonly=True)
    last_fetch = fields.Datetime(string="Last Fetch",readonly=True)

    # provider = self.env['payment.provider'].search(
    #                 [('code', '=', 'stripe'), ('company_id', '=', self.company_id.id), ('state', '!=', 'disabled')],
    #                 limit=1)
    #             if not provider:
    #                 raise UserError('The Stripe payment provider is not configured or disabled.')

    def action_fetch_transactions(self):
        return  {
            'type': 'ir.actions.act_window',
            'res_model': 'fetch.transaction.wiz',
            'view_mode': 'form',
            'target': 'new',
        }

    def cron_fetch_transactions(self):
        """
        Scheduled task: call Stripe and create bank statement lines.
        """
        provider = self.env['payment.provider'].search(
            [('code', '=', 'stripe'), ('state', '!=', 'disabled')],
            limit=1)
        if not provider:
            raise UserError('The Stripe payment provider is not configured or disabled.')

        payload = {
            'limit': 100
        }
        try:
            # list balance transactions (most recent first)
            transactions = provider._stripe_make_request('balance_transactions', payload=payload, method='GET')
            if transactions:
                # pass the journal that should be used (for now search the journal named 'Stripe' as before)
                stripe_journal = self.env['account.journal'].search([('name', '=', 'Stripe')], limit=1)
                if not stripe_journal:
                    raise UserError("Please configure a bank journal named 'Stripe'.")
                # transactions can be a dict with 'data' key or a list
                tx_list = transactions.get('data') if isinstance(transactions, dict) else transactions
                self._create_bank_statements_from_transactions(stripe_journal, tx_list)
                # update last_fetch
                self.last_fetch = fields.Datetime.now()
        except Exception as e:
            # keep error user-friendly for logs
            print("error occurred")
            raise UserError(f"Stripe API request failed: {str(e)}")

    def _create_bank_statements_from_transactions(self, journal, transactions):
        """
        Convert Stripe transactions into Odoo account.bank.statement + lines.
        Handles charge, refund, payout, and fee breakdown.
        Prevents duplicates, assigns accounts, and is ready for reconciliation.
        """
        if not transactions:
            return

        BankStatement = self.env['account.bank.statement']
        BankStatementLine = self.env['account.bank.statement.line']
        Partner = self.env['res.partner']

        # Map common accounts
        receivable_account = Partner.property_account_receivable_id
        bank_account = journal.default_account_id
        if not bank_account:
            raise UserError(f"The journal '{journal.name}' has no bank account set (default_account_id).")
        fees_account = self.env['account.account'].search([
            ('company_id', '=', journal.company_id.id),
            ('name', 'ilike', 'Stripe Fees')
        ], limit=1)

        if not fees_account:
            # fallback: use miscellaneous expenses
            fees_account = self.env['account.account'].search([
                ('company_id', '=', journal.company_id.id),
                ('user_type_id.type', '=', 'expense')
            ], limit=1)

        # Group by date
        tx_by_date = {}
        for tx in transactions:
            created_ts = tx.get('created') or tx.get('created_at')
            if not created_ts:
                continue
            tx_date = datetime.utcfromtimestamp(int(created_ts)).date()
            tx_by_date.setdefault(tx_date, []).append(tx)

        for st_date, txs in tx_by_date.items():
            # Find or create statement for that date
            statement = BankStatement.search([
                ('journal_id', '=', journal.id),
                ('date', '=', st_date),
            ], limit=1)
            if not statement:
                statement = BankStatement.create({
                    'journal_id': journal.id,
                    'name': f"Stripe {st_date.isoformat()}",
                    'date': st_date,
                    'company_id': journal.company_id.id,
                })

            for tx in txs:
                tx_id = tx.get('id') or tx.get('source')
                if not tx_id:
                    continue

                # Skip duplicates
                existing = BankStatementLine.search([
                    ('payment_ref', '=', tx_id),
                    ('statement_id.journal_id', '=', journal.id),
                ], limit=1)
                if existing:
                    continue

                amount_cents = tx.get('amount') or 0
                fee_cents = tx.get('fee') or 0
                gross_amount = float(amount_cents) / 100.0
                fee_amount = float(fee_cents) / 100.0 if fee_cents else 0.0

                tx_type = tx.get('type') or ''
                source = tx.get('source') or tx.get('id') or ''
                description = tx.get('description') or tx.get('reporting_category') or f"{tx_type} {source}"

                # Find partner if possible
                partner = None
                customer_id = tx.get('customer') or (tx.get('source_obj') and tx.get('source_obj').get('customer'))
                if customer_id:
                    partner = Partner.search([('stripe_customer_id', '=', customer_id)], limit=1)

                line_vals = {
                    'statement_id': statement.id,
                    'date': st_date,
                    'payment_ref': tx_id,
                    'ref': source,
                }

                # ---- Handle by type ----
                if tx_type == 'charge':
                    # Gross amount (Receivable)
                    BankStatementLine.create({
                        **line_vals,
                        'name': f"{description} (Gross)",
                        'amount': gross_amount,
                        'partner_id': partner.id if partner else False,
                        'account_id': receivable_account.id,
                    })
                    # Fee
                    if fee_amount:
                        BankStatementLine.create({
                            **line_vals,
                            'name': f"Stripe Fee {source}",
                            'amount': -fee_amount,
                            'account_id': fees_account.id,
                        })

                elif tx_type == 'refund':
                    BankStatementLine.create({
                        **line_vals,
                        'name': f"Refund {description}",
                        'amount': -gross_amount,
                        'partner_id': partner.id if partner else False,
                        'account_id': receivable_account.id,
                    })

                elif tx_type == 'payout':
                    BankStatementLine.create({
                        **line_vals,
                        'name': f"Payout {description}",
                        'amount': -gross_amount,  # money leaves Stripe balance to real bank
                        'account_id': bank_account.id,
                    })

                else:
                    # default fallback (net only)
                    net_amount = (amount_cents - fee_cents) / 100.0
                    BankStatementLine.create({
                        **line_vals,
                        'name': f"{description} (Net)",
                        'amount': net_amount,
                        'partner_id': partner.id if partner else False,
                        'account_id': bank_account.id,
                    })

        return True