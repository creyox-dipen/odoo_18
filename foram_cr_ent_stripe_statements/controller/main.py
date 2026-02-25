# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
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
                    stripe_fee_account = provider.stripe_fees_expense_account_id

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
                        "counterpart_account_id": stripe_fee_account.id,
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
        logger.info("Handling refund for refund %s", stripe_object.get("id"))

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
        
        logger.info("Transaction found: %s (ID: %s)", transaction.reference if transaction else None, transaction.id if transaction else None)
        
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

        # Fetch balance transaction to get net amount
        balance_transaction_id = stripe_object.get("balance_transaction")
        if not balance_transaction_id:
            logger.info(
                "No balance transaction found for refund ID: %s",
                stripe_object.get("id"),
            )
            return 
        
        journal_currency = journal.currency_id or journal.company_id.currency_id
        
        try:
            bt = stripe.BalanceTransaction.retrieve(balance_transaction_id)
            net_amount = bt.get("net", 0) / 100.0 
            refund_amount = stripe_object.get("amount", 0) / 100.0
            fee_amount = bt.get("fee", 0) / 100.0
            currency_code = bt.get("currency", "usd").upper()
            
            # Handle currency
            refund_currency = (
                env["res.currency"]
                .sudo()
                .search([("name", "=", currency_code)], limit=1)
            )
            if not refund_currency:
                raise ValidationError(f"Currency {currency_code} not found in Odoo") 
            
            logger.info("Refund Currency: %s, Journal Currency: %s", refund_currency.name, journal_currency.name)

            # Convert net amount to journal currency
            if refund_currency == journal_currency:
                amount = -refund_amount
                amount_currency = 0.0
                foreign_currency_id = False
            else:
                amount = refund_currency._convert(
                    -refund_amount, journal_currency, journal.company_id, refund_date
                )
                amount_currency = -refund_amount
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
            
            logger.info("Creating refund statement line with amount: %s for partner: %s", 
                       amount, transaction.partner_id.name if transaction.partner_id else "No Partner")
            
            refund_line = env["account.bank.statement.line"].sudo().create(line_vals)
            logger.info("Refund statement line created: ID %s", refund_line.id)
            
            # ===== IMPROVED RECONCILIATION LOGIC =====
            if transaction and refund_line:
                try:
                    credit_note = None
                    
                    # Method 1: Find credit note through payment reference in description
                    description = stripe_object.get("description") or ""
                    logger.info("Searching for credit note using description: %s", description)
                    
                    if description:
                        invoice_ref = description.split("-")[0] if "-" in description else description
                        logger.info("Looking for invoice/credit note with reference: %s", invoice_ref)
                        
                        credit_note = env["account.move"].sudo().search([
                            ("move_type", "=", "out_refund"),
                            ("state", "=", "posted"),
                            "|",
                            ("name", "ilike", invoice_ref),
                            ("ref", "ilike", invoice_ref),
                            ("partner_id", "=", transaction.partner_id.id if transaction.partner_id else False)
                        ], limit=1)
                        
                        if credit_note:
                            logger.info("Found credit note via description: %s", credit_note.name)
                    
                    # Method 2: Find through source_transaction_id
                    if not credit_note:
                        logger.info("Trying to find credit note through source_transaction_id")
                        source_doc = transaction.source_transaction_id
                        
                        if source_doc:
                            logger.info("Source document: %s (model: %s)", 
                                       source_doc.name if hasattr(source_doc, 'name') else source_doc, 
                                       source_doc._name)
                            
                            if hasattr(source_doc, 'invoice_ids'):
                                credit_note = source_doc.invoice_ids.filtered(
                                    lambda inv: inv.move_type == 'out_refund' 
                                    and inv.state == 'posted'
                                )
                                if credit_note:
                                    logger.info("Found credit note via source_doc.invoice_ids: %s", credit_note.name)
                            
                            elif source_doc._name == 'account.move' and source_doc.move_type == 'out_refund':
                                credit_note = source_doc
                                logger.info("Source document IS the credit note: %s", credit_note.name)
                    
                    # Method 3: Find through payment
                    if not credit_note and transaction.payment_id:
                        logger.info("Trying to find credit note through payment: %s", transaction.payment_id.name)
                        payment = transaction.payment_id
                        
                        if payment.reconciled_invoice_ids:
                            credit_note = payment.reconciled_invoice_ids.filtered(
                                lambda inv: inv.move_type == 'out_refund' 
                                and inv.state == 'posted'
                            )
                            if credit_note:
                                logger.info("Found credit note via payment.reconciled_invoice_ids: %s", credit_note.name)
                        
                        if not credit_note:
                            payment_lines = payment.move_id.line_ids.filtered(
                                lambda l: l.account_id.account_type == 'asset_receivable'
                            )
                            for line in payment_lines:
                                if line.matched_debit_ids or line.matched_credit_ids:
                                    for match in (line.matched_debit_ids + line.matched_credit_ids):
                                        matched_line = match.debit_move_id if match.debit_move_id != line else match.credit_move_id
                                        if matched_line.move_id.move_type == 'out_refund':
                                            credit_note = matched_line.move_id
                                            logger.info("Found credit note via payment line matching: %s", credit_note.name)
                                            break
                                if credit_note:
                                    break
                    
                    # Method 4: Search by partner and amount
                    if not credit_note and transaction.partner_id:
                        logger.info("Searching for credit note by partner and amount")
                        credit_note = env["account.move"].sudo().search([
                            ("move_type", "=", "out_refund"),
                            ("state", "=", "posted"),
                            ("partner_id", "=", transaction.partner_id.id),
                            ("amount_total", "=", abs(amount))
                        ], limit=1, order="date desc")
                        
                        if credit_note:
                            logger.info("Found credit note by partner and amount: %s", credit_note.name)
                    
                    if not credit_note:
                        logger.warning("Could not find credit note for refund transaction: %s", transaction.reference)
                    else:
                        logger.info("Processing reconciliation for credit note: %s (payment_state: %s)", 
                                   credit_note.name, credit_note.payment_state)
                        
                        # Get unreconciled receivable lines from the credit note
                        receivable_lines = credit_note.line_ids.filtered(
                            lambda l: l.account_id.account_type == 'asset_receivable' 
                            and not l.reconciled
                            and l.balance != 0
                        )
                        
                        logger.info("Found %s unreconciled receivable lines", len(receivable_lines))
                        
                        if receivable_lines:
                            # Credit note NOT yet paid - reconcile directly with credit note
                            logger.info("Attempting automatic reconciliation using bank.rec.widget")
                            
                            wizard = env['bank.rec.widget'].sudo().with_context(
                                default_st_line_id=refund_line.id
                            ).new({})
                            
                            wizard._action_trigger_matching_rules()
                            logger.info("Wizard state after trigger_matching_rules: %s", wizard.state)
                            
                            if wizard.state != 'valid':
                                logger.info("Manual matching required, adding receivable line")
                                wizard.line_ids = [(0, 0, {
                                    'source_aml_id': receivable_lines[0].id,
                                })]
                                logger.info("Wizard state after manual line addition: %s", wizard.state)
                            
                            if wizard.state == 'valid':
                                wizard._action_validate()
                                logger.info("✓ Successfully reconciled statement line %s with credit note %s",
                                           refund_line.ref, credit_note.name)
                                
                                credit_note.message_post(
                                    body=f"Automatically reconciled with Stripe refund statement line (Ref: {refund_line.ref})"
                                )
                            else:
                                logger.warning("Wizard state is not valid (%s), cannot auto-reconcile. Manual reconciliation required.", 
                                             wizard.state)
                        else:
                            # Credit note receivable is ALREADY reconciled (payment was made)
                            # We need to reconcile the bank statement with the payment instead
                            logger.info("Credit note receivable already reconciled - looking for payment to reconcile with")
                            logger.info("Credit note line details:")
                            for line in credit_note.line_ids:
                                logger.info("  - Account: %s, Balance: %s, Reconciled: %s", 
                                           line.account_id.code, line.balance, line.reconciled)
                            
                            # Find the payment that reconciled the credit note
                            reconciled_receivable = credit_note.line_ids.filtered(
                                lambda l: l.account_id.account_type == 'asset_receivable' and l.reconciled
                            )
                            
                            if reconciled_receivable:
                                logger.info("Found reconciled receivable line, looking for payment")
                                
                                # Get the payment through matched partials
                                payment_move = None
                                for partial in (reconciled_receivable.matched_debit_ids + reconciled_receivable.matched_credit_ids):
                                    # The other line in the partial is from the payment
                                    other_line = partial.debit_move_id if partial.debit_move_id != reconciled_receivable else partial.credit_move_id
                                    
                                    # Check if this is a payment journal entry
                                    payment = env['account.payment'].sudo().search([('move_id', '=', other_line.move_id.id)], limit=1)
                                    if payment or other_line.move_id.statement_line_id:

                                        payment_move = other_line.move_id
                                        logger.info("Found payment move: %s", payment_move.name)
                                        break
                                
                                if payment_move:
                                    # Now find the liquidity line from this payment that needs to be reconciled with our statement
                                    # For outbound payments (refunds), we're looking for the Outstanding Payment line
                                    payment_outstanding_lines = payment_move.line_ids.filtered(
                                        lambda l: l.account_id.code == '101404'  # Outstanding Payment account
                                        and not l.reconciled
                                        and l.balance != 0
                                    )
                                    
                                    logger.info("Found %s unreconciled outstanding payment lines in payment move", len(payment_outstanding_lines))
                                    
                                    if payment_outstanding_lines:
                                        logger.info("Attempting to reconcile bank statement with payment outstanding line")
                                        
                                        # Use bank reconciliation widget
                                        wizard = env['bank.rec.widget'].sudo().with_context(
                                            default_st_line_id=refund_line.id
                                        ).new({})
                                        
                                        # Trigger automatic matching first
                                        wizard._action_trigger_matching_rules()
                                        logger.info("Wizard state after trigger_matching_rules: %s", wizard.state)
                                        
                                        # If not auto-matched, manually add the payment outstanding line
                                        if wizard.state not in ['valid', 'reconciled']:
                                            logger.info("Manual matching required, adding payment outstanding line")
                                            wizard.line_ids = [(0, 0, {
                                                'source_aml_id': payment_outstanding_lines[0].id,
                                            })]
                                            logger.info("Wizard state after manual line addition: %s", wizard.state)
                                        
                                        # Validate the reconciliation
                                        # Validate the reconciliation
                                        # Validate the reconciliation
                                        if wizard.state in ['valid', 'reconciled']:
                                            wizard._action_validate()
                                            logger.info("✓ Successfully reconciled statement line %s with payment %s",
                                                       refund_line.ref, payment_move.name)
                                            
                                            # Find and update the payment record
                                            payment = env['account.payment'].sudo().search([('move_id', '=', payment_move.id)], limit=1)
                                            if payment:
                                                try:
                                                    # CRITICAL: Mark payment as matched - this is what _compute_payment_state checks
                                                    payment.write({
                                                        'is_matched': True,
                                                        'is_reconciled': True
                                                    })
                                                    
                                                    # FLUSH to database immediately so the SQL query in _compute_payment_state sees it
                                                    env.cr.flush()
                                                    
                                                    logger.info("Marked payment %s as matched and reconciled", payment.name)
                                                    
                                                except Exception as payment_error:
                                                    logger.warning("Could not update payment: %s", str(payment_error))
                                            
                                            # Force recompute of credit note payment state
                                            try:
                                                # Invalidate cache to force recomputation
                                                credit_note.invalidate_recordset(['payment_state', 'amount_residual', 'amount_residual_signed'])
                                                
                                                # Trigger the compute method AFTER flushing
                                                credit_note._compute_amount()
                                                credit_note._compute_payment_state()
                                                
                                                logger.info("Credit note %s - payment_state: %s, amount_residual: %s",
                                                           credit_note.name, credit_note.payment_state, credit_note.amount_residual)
                                                
                                                # If STILL not paid, force it via direct SQL update
                                                if credit_note.payment_state != 'paid' and credit_note.amount_residual == 0:
                                                    logger.warning("Forcing payment_state to 'paid' via SQL")
                                                    env.cr.execute("""
                                                        UPDATE account_move 
                                                        SET payment_state = 'paid'
                                                        WHERE id = %s
                                                    """, (credit_note.id,))
                                                    credit_note.invalidate_recordset(['payment_state'])
                                                    logger.info("Credit note %s force-updated to paid", credit_note.name)
                                                
                                            except Exception as cn_error:
                                                logger.warning("Could not update credit note: %s", str(cn_error))
                                                import traceback
                                                logger.error(traceback.format_exc())
                                            
                                            # Add notes
                                            refund_line.move_id.sudo().message_post(
                                                body=f"Automatically reconciled with payment {payment_move.name} for credit note {credit_note.name}"
                                            )
                                            credit_note.sudo().message_post(
                                                body=f"Payment confirmed via Stripe refund (Ref: {refund_line.ref}). Payment state: {credit_note.payment_state}"
    )
                                        else:
                                            logger.warning("Wizard state is not valid (%s), cannot auto-reconcile payment. Manual reconciliation required.", 
                                                         wizard.state)
                                         
                                    else:
                                        logger.warning("No unreconciled outstanding payment lines found in payment move")
                                        logger.info("Payment move line details:")
                                        for line in payment_move.line_ids:
                                            logger.info("  - Account: %s, Balance: %s, Reconciled: %s", 
                                                       line.account_id.code, line.balance, line.reconciled)
                                else:
                                    logger.warning("Could not find payment move for reconciled credit note")
                            else:
                                logger.warning("Could not find reconciled receivable line in credit note")
                
                except Exception as reconcile_error:
                    logger.error("Failed to auto-reconcile refund statement line: %s", str(reconcile_error))
                    import traceback
                    logger.error(traceback.format_exc())
                    # Don't fail the whole webhook - user can manually reconcile
            
            # Handle Stripe fee reversal
            stripe_fee_account = provider.stripe_fees_expense_account_id
            if not stripe_fee_account:
                logger.warning("Stripe Fees Expense account not configured, skipping fee reversal")
            elif fee_amount > 0:
                if refund_currency == journal_currency:
                    fee_balance_amount = fee_amount  # POSITIVE → credit expense
                    fee_amount_currency = 0.0
                    fee_foreign_currency_id = False
                else:
                    fee_balance_amount = refund_currency._convert(
                        fee_amount,
                        journal_currency,
                        journal.company_id,
                        refund_date,
                    )
                    fee_amount_currency = fee_amount
                    fee_foreign_currency_id = refund_currency.id
            
                fee_reverse_vals = {
                    "statement_id": statement.id,
                    "date": refund_date,
                    "amount": fee_balance_amount,  # CREDIT expense
                    "foreign_currency_id": fee_foreign_currency_id,
                    "amount_currency": fee_amount_currency,
                    "partner_id": (
                        provider.stripe_fees_partner.id
                        if provider.stripe_fees_partner
                        else False
                    ),
                    "ref": f"{stripe_object.get('id')}-fee",
                    "payment_ref": f"Stripe Fee Reversal (Refund)",
                    "journal_id": journal.id,
                    "counterpart_account_id": stripe_fee_account.id,
                }
            
                env["account.bank.statement.line"].sudo().create(fee_reverse_vals)
                logger.info("Fee reversal line created: %s", fee_balance_amount)

            logger.info("✓ Refund statement processing completed")

        except Exception as e:
            logger.error("Error while handling refund: %s", str(e))
            import traceback
            logger.error(traceback.format_exc())