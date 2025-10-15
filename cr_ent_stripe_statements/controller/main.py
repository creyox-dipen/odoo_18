# controllers/main.py
import logging
import stripe
from odoo import http
from odoo.http import request
from odoo.addons.payment_stripe.controllers.main import StripeController
from datetime import datetime
from odoo.exceptions import ValidationError, UserError

logger = logging.getLogger(__name__)


class StripeStatementCollection(StripeController):

    @http.route(
        StripeController._webhook_url,
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def stripe_webhook(self):
        logger.info("Stripe Webhook called")
        event = request.get_json_data()
        stripe_object = event.get("data", {}).get("object", {})
        logger.info("stripe object : %s", stripe_object)

        # Call the original stripe webhook first (keeps normal logic)
        response = super().stripe_webhook()

        provider = (
            request.env["payment.provider"]
            .sudo()
            .search(
                [("code", "=", "stripe"), ("is_stripe_collection", "=", True)], limit=1
            )
        )
        if not provider:
            return response

        journal = provider.journal_id
        if not journal:
            raise UserError("Please configure a bank journal.")

        event_type = event.get("type")

        if event_type == "charge.succeeded":
            self._handle_charge_succeeded(journal, stripe_object, provider)

        elif event_type == "charge.refunded":
            self._handle_refund(journal, stripe_object, provider)

        elif event_type == "payout.paid":
            self._handle_payout(journal, stripe_object, provider)

        return response

    def _handle_charge_succeeded(self, journal, stripe_object, provider):
        env = request.env
        logger.info(
            "Handling charge.succeeded for charge ID: %s", stripe_object.get("id")
        )

        # Find matching payment.transaction using payment_intent
        request.env["payment.transaction"].sudo()._cron_post_process()
        payment_intent_id = stripe_object.get("payment_intent")
        transaction = (
            env["payment.transaction"]
            .sudo()
            .search(
                [
                    ("provider_reference", "=", payment_intent_id),
                    ("provider_id", "=", provider.id),
                ],
                limit=1,
            )
        )
        logger.info("Transaction: %s", transaction)
        if not transaction:
            logger.warning(
                "No matching payment transaction found for payment_intent: %s",
                payment_intent_id,
            )
            return

        # Set Stripe API key for additional fetches
        stripe.api_key = provider.stripe_secret_key

        # Skip if POS transaction (as per module limitations)
        if (
            transaction.source_transaction_id
            and transaction.source_transaction_id._name == "pos.order"
        ):
            logger.info(
                "Skipping POS reconciliation for transaction: %s", transaction.reference
            )
            return

        # Check for duplicate processing
        logger.info("Id: %s", stripe_object.get("id"))
        existing_line = (
            env["account.bank.statement.line"]
            .sudo()
            .search([("ref", "=", stripe_object.get("id"))], limit=1)
        )
        if existing_line:
            return

        # Get date from created timestamp
        charge_date = datetime.fromtimestamp(stripe_object.get("created")).date()

        # Get or create bank statement for the date
        statement = (
            env["account.bank.statement"]
            .sudo()
            .search(
                [("journal_id", "=", journal.id), ("date", "=", charge_date)], limit=1
            )
        )
        if not statement:
            statement = (
                env["account.bank.statement"]
                .sudo()
                .create(
                    {
                        "name": f"Stripe Statement {charge_date}",
                        "date": charge_date,
                        "journal_id": journal.id,
                    }
                )
            )

        # Fetch balance transaction to get net amount
        balance_transaction_id = stripe_object.get("balance_transaction")
        if not balance_transaction_id:
            logger.info(
                "No balance transaction found for charge ID: %s",
                stripe_object.get("id"),
            )
            return

        try:
            bt = stripe.BalanceTransaction.retrieve(balance_transaction_id)
            amount = charge_amount = (
                stripe_object.get("amount", 0) / 100.0
            )  # Convert from cents
            currency_code = bt.get("currency", "usd").upper()

            # Handle currency
            charge_currency = (
                env["res.currency"]
                .sudo()
                .search([("name", "=", currency_code)], limit=1)
            )
            if not charge_currency:
                raise ValidationError(f"Currency {currency_code} not found in Odoo")

            journal_currency = journal.currency_id or journal.company_id.currency_id

            # Convert net amount to journal currency
            if charge_currency == journal_currency:
                amount = amount
                amount_currency = 0.0
                foreign_currency_id = False
            else:
                amount = charge_currency._convert(
                    amount, journal_currency, journal.company_id, charge_date
                )
                amount_currency = amount
                foreign_currency_id = charge_currency.id

            # Fetch the Outstanding Receipt account
            outstanding_receipt_account = (
                request.env["account.account"]
                .sudo()
                .search(
                    [
                        ("code", "=", "101403"),
                        ("company_ids", "in", [journal.company_id.id]),
                    ],
                    limit=1,
                )
            )

            if not outstanding_receipt_account:
                raise UserError(
                    "Outstanding Receipt account not found for the company!"
                )

            # Create bank statement line for the net amount
            line_vals = {
                "statement_id": statement.id,
                "date": charge_date,
                "amount": amount,
                "foreign_currency_id": foreign_currency_id,
                "amount_currency": amount_currency,
                "partner_id": (
                    transaction.partner_id.id if transaction.partner_id else False
                ),
                "ref": stripe_object.get("id"),
                "payment_ref": stripe_object.get("description") or payment_intent_id,
                "journal_id": journal.id,
                # 'counterpart_account_id': outstanding_receipt_account.id,
            }
            logger.info("Statement ID: %s", statement.id)
            logger.info("Amount: %s", amount)
            logger.info("Foreign Currency ID: %s", foreign_currency_id)
            logger.info("Amount Currency: %s", amount_currency)
            logger.info(
                "Partner ID: %s",
                transaction.partner_id.id if transaction.partner_id else False,
            )
            logger.info("Ref: %s", stripe_object.get("id"))
            logger.info(
                "Payment Ref: %s", stripe_object.get("description") or payment_intent_id
            )

            charge_line = env["account.bank.statement.line"].sudo().create(line_vals)

            # Create fee line
            balance_transaction_id = stripe_object.get("balance_transaction")
            if balance_transaction_id:
                try:
                    bt = stripe.BalanceTransaction.retrieve(balance_transaction_id)
                    fee_amount = bt.get("fee", 0) / 100.0  # Convert from cents
                    fee_currency_code = bt.get("currency", "usd").upper()
                    fee_currency = (
                        env["res.currency"]
                        .sudo()
                        .search([("name", "=", fee_currency_code)], limit=1)
                    )

                    if fee_currency == journal_currency:
                        fee_balance_amount = -fee_amount  # Negative for fee
                        fee_amount_currency = 0.0
                        fee_foreign_currency_id = False
                    else:
                        fee_balance_amount = fee_currency._convert(
                            -fee_amount,
                            journal_currency,
                            journal.company_id,
                            charge_date,
                        )
                        fee_amount_currency = -fee_amount
                        fee_foreign_currency_id = fee_currency.id

                    # Create separate line for fee
                    partner_payble_account = (
                        provider.stripe_fees_partner.property_account_payable_id.id
                    )
                    fee_line_vals = {
                        "statement_id": statement.id,
                        "date": charge_date,
                        "amount": fee_balance_amount,
                        "foreign_currency_id": fee_foreign_currency_id,
                        "amount_currency": fee_amount_currency,
                        "partner_id": (
                            provider.stripe_fees_partner.id
                            if provider.stripe_fees_partner
                            else False
                        ),
                        "ref": bt.get("id"),
                        "payment_ref": f"Stripe Fee for {stripe_object.get('id')}",
                        "journal_id": journal.id,
                        "counterpart_account_id": partner_payble_account,
                    }
                    fee_line = (
                        env["account.bank.statement.line"].sudo().create(fee_line_vals)
                    )

                except Exception as e:
                    logger.info("Error while handling charge: %s", str(e))

            logger.info("Statement Created")

        except Exception as e:
            logger.info("Error while handling charge: %s", str(e))

    def _handle_refund(self, journal, stripe_object, provider):
        env = request.env
        logger.info("Handling refund for refund ID: %s", stripe_object.get("id"))

        # Find matching payment.transaction using payment_intent or charge
        payment_intent_id = stripe_object.get("payment_intent")
        charge_id = stripe_object.get("charge")
        transaction = (
            env["payment.transaction"]
            .sudo()
            .search(
                [
                    "|",
                    ("provider_reference", "=", payment_intent_id),
                    ("provider_reference", "=", charge_id),
                    ("provider_id", "=", provider.id),
                ],
                limit=1,
            )
        )
        if not transaction:
            # If not found, try searching for refund-specific transaction
            transaction = (
                env["payment.transaction"]
                .sudo()
                .search(
                    [
                        ("provider_reference", "=", stripe_object.get("id")),
                        ("operation", "=", "refund"),
                        ("provider_id", "=", provider.id),
                    ],
                    limit=1,
                )
            )
        logger.info("Transaction: %s", transaction)
        if not transaction:
            logger.warning(
                "No matching payment transaction found for refund ID: %s",
                stripe_object.get("id"),
            )
            return

        # Set Stripe API key for any additional fetches
        stripe.api_key = provider.stripe_secret_key

        # Skip if POS transaction (check original if refund)
        source_transaction = transaction.source_transaction_id or transaction
        if (
            source_transaction.source_transaction_id
            and source_transaction.source_transaction_id._name == "pos.order"
        ):
            logger.info(
                "Skipping POS reconciliation for transaction: %s", transaction.reference
            )
            return

        # Get date from created timestamp
        refund_date = datetime.fromtimestamp(stripe_object.get("created")).date()

        # Get or create bank statement for the date
        statement = (
            env["account.bank.statement"]
            .sudo()
            .search(
                [("journal_id", "=", journal.id), ("date", "=", refund_date)], limit=1
            )
        )
        if not statement:
            statement = (
                env["account.bank.statement"]
                .sudo()
                .create(
                    {
                        "name": f"Stripe Statement {refund_date}",
                        "date": refund_date,
                        "journal_id": journal.id,
                    }
                )
            )

        # Fetch balance transaction to get net amount (usually negative refund amount, fee=0)
        balance_transaction_id = stripe_object.get("balance_transaction")
        if not balance_transaction_id:
            logger.info(
                "No balance transaction found for refund ID: %s",
                stripe_object.get("id"),
            )
            return

        try:
            bt = stripe.BalanceTransaction.retrieve(balance_transaction_id)
            net_amount = bt.get("net", 0) / 100.0  # Negative for refund
            fee_amount = bt.get("fee", 0) / 100.0  # Usually 0 for refunds
            currency_code = bt.get("currency", "usd").upper()

            # Handle currency
            refund_currency = (
                env["res.currency"]
                .sudo()
                .search([("name", "=", currency_code)], limit=1)
            )
            if not refund_currency:
                raise ValidationError(f"Currency {currency_code} not found in Odoo")

            journal_currency = journal.currency_id or journal.company_id.currency_id
            logger.info("Currency: %s", journal_currency)

            # Convert net amount to journal currency
            if refund_currency == journal_currency:
                amount = -net_amount
                amount_currency = 0.0
                foreign_currency_id = False
            else:
                amount = refund_currency._convert(
                    -net_amount, journal_currency, journal.company_id, refund_date
                )
                amount_currency = -net_amount
                foreign_currency_id = refund_currency.id

            outstanding_payment_account = (
                request.env["account.account"]
                .sudo()
                .search(
                    [
                        ("code", "=", "101404"),
                        ("company_ids", "in", [journal.company_id.id]),
                    ],
                    limit=1,
                )
            )

            # Create bank statement line for the net refund amount (negative)
            line_vals = {
                "statement_id": statement.id,
                "date": refund_date,
                "amount": amount,
                "foreign_currency_id": foreign_currency_id,
                "amount_currency": amount_currency,
                "partner_id": (
                    transaction.partner_id.id if transaction.partner_id else False
                ),
                "ref": stripe_object.get("id"),
                "payment_ref": f"Refund for {charge_id or payment_intent_id}",
                "journal_id": journal.id,
                "counterpart_account_id": outstanding_payment_account.id,
            }
            logger.info("Statement ID: %s", statement.id)
            logger.info("Amount: %s", amount)
            logger.info("Foreign Currency ID: %s", foreign_currency_id)
            logger.info("Amount Currency: %s", amount_currency)
            logger.info(
                "Partner ID: %s",
                transaction.partner_id.id if transaction.partner_id else False,
            )
            logger.info("Ref: %s", stripe_object.get("id"))
            logger.info("Payment Ref: %s", line_vals["payment_ref"])

            refund_line = env["account.bank.statement.line"].sudo().create(line_vals)
            logger.info("Statement Created")

        except Exception as e:
            logger.info("Error while handling refund: %s", str(e))

    def _handle_payout(self, journal, stripe_object, provider):
        env = request.env
        logger.info("Handling payout for payout ID: %s", stripe_object.get("id"))

        # Set Stripe API key for additional fetches
        stripe.api_key = provider.stripe_secret_key

        # Check for duplicate processing
        existing_move = (
            env["account.move"]
            .sudo()
            .search([("ref", "=", stripe_object.get("id"))], limit=1)
        )
        if existing_move:
            logger.info("Duplicate payout event for ID: %s", stripe_object.get("id"))
            return

        # Get date from arrival_date if available, else created timestamp
        arrival_timestamp = stripe_object.get("arrival_date")
        if arrival_timestamp:
            payout_date = datetime.fromtimestamp(arrival_timestamp).date()
        else:
            payout_date = datetime.fromtimestamp(stripe_object.get("created")).date()

        try:
            balance_transaction_id = stripe_object.get("balance_transaction")
            bt = stripe.BalanceTransaction.retrieve(balance_transaction_id)
            logger.info("BT : %d", bt)
            net_cents = bt.get("net", 0)
            logger.info("NET : %d", net_cents)
            net_amount = (
                -net_cents / 100.0
            )  # Make positive for transfer amount (since net is negative for payouts)
            currency_code = bt.get("currency", "usd").upper()

            # Handle currency
            charge_currency = (
                env["res.currency"]
                .sudo()
                .search([("name", "=", currency_code)], limit=1)
            )
            if not charge_currency:
                raise ValidationError(f"Currency {currency_code} not found in Odoo")

            journal_currency = journal.currency_id or journal.company_id.currency_id

            # Convert net amount to journal currency
            if charge_currency == journal_currency:
                net_balance_amount = net_amount
                net_amount_currency = 0.0
                net_foreign_currency_id = False
            else:
                net_balance_amount = charge_currency._convert(
                    net_amount, journal_currency, journal.company_id, payout_date
                )
            net_amount_currency = net_amount
            net_foreign_currency_id = charge_currency.id

            net_currency_id = net_foreign_currency_id or journal_currency.id

            source_account = journal.default_account_id
            destination_account = provider.transfer_account

            if not source_account or not destination_account:
                return

            # Create journal entry for internal transfer (in source journal)
            transfer_move_vals = {
                "journal_id": journal.id,  # Source journal (Stripe)
                "date": payout_date,
                "ref": f"Internal Transfer for {stripe_object.get('id')}",
                "move_type": "entry",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": f"Internal Transfer for {stripe_object.get('id')}",
                            "account_id": source_account.id,  # Stripe liquidity
                            "debit": 0.0,
                            "credit": net_balance_amount,  # Money leaves source
                            "currency_id": net_currency_id,
                            "amount_currency": -net_amount_currency,  # Negative for credit
                            "partner_id": False,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": f"Internal Transfer for {stripe_object.get('id')}",
                            "account_id": destination_account.id,  # Bank liquidity
                            "debit": net_balance_amount,  # Money arrives in destination
                            "credit": 0.0,
                            "currency_id": net_currency_id,
                            "amount_currency": net_amount_currency,
                            "partner_id": False,
                        },
                    ),
                ],
            }
            transfer_move = (
                request.env["account.move"].sudo().create(transfer_move_vals)
            )
            transfer_move.action_post()

            logger.info("Internal Transfer Journal Entry Created")

        except Exception as e:
            logger.info("Error while handling payout: %s", str(e))
