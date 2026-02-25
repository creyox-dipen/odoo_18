# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import chargebee
from datetime import datetime
import logging
import json
from datetime import datetime

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    chargebee_id = fields.Char(string="Chargebee Invoice ID", help="ID of the invoice in Chargebee")
    chargebee_invoice_url = fields.Char(string="Chargebee Invoice URL", help="Link to the invoice in Chargebee")
    linked_payments = fields.Text(string="Linked Payments", help="Details of linked payments stored as JSON")
    adjustments = fields.Text(string="Adjustments", help="Adjustment credit notes stored as JSON")

    def convert_timestamp_to_datetime(self, timestamp):
        """Convert a timestamp to a datetime object."""
        if timestamp:
            return fields.Datetime.to_string(datetime.utcfromtimestamp(timestamp))
        return None

    def convert_timestamp_to_utc(timestamp):
        """Convert Unix timestamp to UTC datetime."""
        if timestamp:
            try:
                return datetime.utcfromtimestamp(timestamp)
            except (ValueError, OSError):
                _logger.error(f"Invalid timestamp: {timestamp}")
                return None
        return None

    def _is_reconciled(self):
        """Check if a journal entry is fully reconciled."""
        return all(line.reconciled for line in self.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        invoices = super(AccountMove, self).create(vals_list)
        chargebee_config = self.env['chargebee.configuration'].search([], limit=1)

        if not chargebee_config or not chargebee_config.api_key or not chargebee_config.site_name:
            raise UserError(_("Chargebee configuration is incomplete."))

        # Configure Chargebee
        chargebee.configure(chargebee_config.api_key, chargebee_config.site_name)

        for invoice in invoices:
            if invoice.chargebee_id:
                try:
                    # Skip reconciled invoices
                    if invoice._is_reconciled():
                        _logger.info(f"Skipping reconciled invoice: {invoice.chargebee_id}")
                        continue

                    # Sync credit notes
                    self.sync_credit_notes(invoice)

                    # Fetch payment details from Chargebee
                    payments = chargebee.Transaction.list({"invoice_id": invoice.chargebee_id})
                    total_paid = 0

                    for payment_data in payments:
                        payment = payment_data.transaction
                        payment_date = self.convert_timestamp_to_datetime(payment.date)
                        payment_amount = payment.amount / 100  # Convert cents to currency

                        # Create payment in Odoo
                        payment_vals = {
                            'partner_id': invoice.partner_id.id,
                            'amount': payment_amount,
                            'date': payment_date,
                            'payment_type': 'inbound',
                            'journal_id': self.env['account.journal'].search([('type', '=', 'bank')], limit=1).id,
                            'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                            'communication': f"Chargebee Payment: {payment.id}",
                            'move_id': invoice.id,
                        }
                        odoo_payment = self.env['account.payment.register'].create(payment_vals)
                        odoo_payment.action_post()
                        odoo_payment.action_create_payments()
                        total_paid += payment_amount

                    # Reconcile payments if fully paid
                    if total_paid >= invoice.amount_total:
                        invoice.action_post()
                        invoice.action_create_payments()
                        invoice.action_invoice_paid()

                    _logger.info(
                        f"Payments automatically managed for invoice {invoice.chargebee_id}. Total paid: {total_paid}")
                except chargebee.APIError as e:
                    _logger.error(f"Error syncing payments for invoice {invoice.chargebee_id}: {e.json_obj}")
                except Exception as e:
                    _logger.error(f"Error managing payments for invoice {invoice.chargebee_id}: {e}")

        return invoices

    def action_sync_credit_notes(self):
        """Sync only credit notes from Chargebee."""
        chargebee_config = self.env['chargebee.configuration'].search([], limit=1)
        if not chargebee_config or not chargebee_config.api_key or not chargebee_config.site_name:
            raise UserError(_("Chargebee configuration is incomplete."))

        chargebee.configure(chargebee_config.api_key, chargebee_config.site_name)
        try:
            _logger.info("Starting Chargebee credit note sync...")
            credit_notes = chargebee.CreditNote.list()
            for credit_note_data in credit_notes:
                credit_note = credit_note_data.credit_note

                # Check if the credit note already exists
                existing_cn = self.env['account.move'].search([('chargebee_id', '=', credit_note.id)], limit=1)
                if existing_cn:
                    _logger.info(f"Credit note {existing_cn.name} already exists. Skipping.")
                    continue

                # Prepare credit note lines
                credit_note_lines = [
                    (0, 0, {
                        'name': line.description,
                        'quantity': 1,
                        'price_unit': -(line.amount / 100),  # Negative for credit notes
                    })
                    for line in credit_note.line_items
                ]

                # Create credit note
                self.env['account.move'].create({
                    'move_type': 'out_refund',
                    'partner_id': self._get_or_create_partner(credit_note).id,
                    'chargebee_id': credit_note.id,
                    'invoice_date': fields.Datetime.to_string(datetime.utcfromtimestamp(credit_note.date)),
                    'invoice_line_ids': credit_note_lines,
                })
            _logger.info("Credit note sync completed successfully.")
        except Exception as e:
            _logger.error(f"Error syncing credit notes: {e}")
            raise UserError(_("An error occurred while syncing credit notes. Please check the logs for details."))

    def sync_credit_notes(self, invoice):
        """Fetch and sync credit notes related to an invoice."""
        try:
            credit_notes = chargebee.CreditNote.list({"invoice_id": invoice.chargebee_id})
            for credit_note_data in credit_notes:
                credit_note = credit_note_data.credit_note

                # Check if the credit note already exists
                existing_cn = self.env['account.move'].search([('chargebee_id', '=', credit_note.id)], limit=1)

                if not existing_cn:
                    # Prepare credit note lines
                    credit_note_lines = [
                        (0, 0, {
                            'name': line.description,
                            'quantity': 1,
                            'price_unit': line.amount / 100,  # Negative for credit notes
                            'tax_ids': [],  # Populate tax_ids if applicable
                        })
                        for line in credit_note.line_items
                    ]

                    # Create credit note in Odoo
                    self.env['account.move'].create({
                        'move_type': 'out_refund',
                        'partner_id': invoice.partner_id.id,
                        'chargebee_id': credit_note.id,
                        'invoice_date': self.convert_timestamp_to_datetime(credit_note.date),
                        'line_ids': credit_note_lines,
                    })
                else:
                    _logger.info(f"Credit note {credit_note.id} already exists for invoice {invoice.chargebee_id}.")
        except chargebee.APIError as e:
            _logger.error(f"Error syncing credit notes for invoice {invoice.chargebee_id}: {e.json_obj}")
            raise UserError(_("Failed to sync credit notes. Error: %s") % e.json_obj.get('message', str(e)))
        except Exception as e:
            _logger.error(f"Error syncing credit notes for invoice {invoice.chargebee_id}: {e}")
            raise UserError(_("An error occurred while syncing credit notes. Please check the logs for details."))

    def action_sync_account_invoices(self):
        """Sync invoices from Chargebee and create products if they do not exist."""
        chargebee_config = self.env['chargebee.configuration'].search([], limit=1)
        if not chargebee_config or not chargebee_config.api_key or not chargebee_config.site_name:
            raise UserError(_("Chargebee configuration is incomplete."))

        # Configure Chargebee
        chargebee.configure(chargebee_config.api_key, chargebee_config.site_name)

        try:
            start_time = datetime.now()
            total_records = 0
            invoices = chargebee.Invoice.list()
            for inv_data in invoices:
                invoice = inv_data.invoice

                # Check if the invoice already exists
                existing_invoice = self.search([('chargebee_id', '=', invoice.id)], limit=1)
                if existing_invoice and existing_invoice.state == 'posted':
                    _logger.info(f"Skipping reconciled invoice: {existing_invoice.name}")
                    continue

                # Prepare line items and create products if needed
                line_items = []
                for item in getattr(invoice, 'line_items', []):
                    # Check if the product exists
                    product = self.env['product.product'].search([('default_code', '=', item.id)], limit=1)
                    if not product:
                        # Create product if it doesn't exist
                        product = self.env['product.product'].create({
                            'name': item.description or "Chargebee Product",
                            'default_code': item.id,
                            'list_price': item.unit_amount / 100,  # Default price from Chargebee
                            'type': 'service',  # Or 'consu'/'product' based on your needs
                        })
                        _logger.info(f"Created product {product.name} with Chargebee ID {item.id}.")

                    # Prepare the line item
                    line_items.append((0, 0, {
                        'name': item.description or "Chargebee Item",
                        'quantity': item.quantity,
                        'price_unit': item.unit_amount / 100,  # Convert cents to currency
                        'product_id': product.id,
                        'tax_ids': [],  # Populate tax_ids if applicable
                    }))

                # Prepare invoice values
                vals = {
                    'move_type': 'out_invoice',
                    'invoice_date': self.convert_timestamp_to_datetime(invoice.date),
                    'invoice_date_due': self.convert_timestamp_to_datetime(invoice.due_date),
                    'partner_id': self._get_or_create_partner(invoice).id,
                    'chargebee_id': invoice.id,
                    'invoice_line_ids': line_items,
                }

                # Create or update invoice
                if existing_invoice:
                    try:
                        existing_invoice.write(vals)
                    except Exception as e:
                        _logger.warning(f"Could not update reconciled invoice {existing_invoice.name}: {e}")
                else:
                    odoo_invoice = self.create(vals)
                    super(AccountMove, odoo_invoice).action_post()
                self.env.cr.commit()
                # Increment the total record count
                total_records += 1

                # Handle linked payments for paid invoices
                if invoice.status == 'paid' and invoice.linked_payments:
                    self._register_chargebee_payment(odoo_invoice, invoice.linked_payments)
                    self.env.cr.commit()
            # Log successful data processing
            self.env['cr.data.processing.log'].sudo()._log_data_processing(
                        table_name='Account Invoice',
                        record_count=total_records,
                        status='success',
                        timespan=str(datetime.now() - start_time),
                        initiated_at=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                        cr_configuration_id=chargebee_config.id,
                        context='invoices',  # Specify context for this page
                    )

        except Exception as e:
            _logger.error(f"Error syncing invoices: {e}")
            # Log the failure of data processing
            self.env['cr.data.processing.log'].sudo()._log_data_processing(
                table_name='Account Invoice',
                record_count=total_records,
                status='failure',
                timespan=str(datetime.now() - start_time),
                initiated_at=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                cr_configuration_id=chargebee_config.id,
                error_message=str(e),
                context='invoices',  # Specify context for this page
            )
            raise UserError(_("An error occurred while syncing invoices. Please check the logs for details."))

    def _register_chargebee_payment(self, odoo_invoice, linked_payments):
        """Register payments for a synced Chargebee invoice."""
        PaymentRegister = self.env['account.payment.register']
        for payment_data in linked_payments:
            payment_date = self.convert_timestamp_to_datetime(payment_data.txn_date)  # Convert timestamp to date
            payment_amount = payment_data.applied_amount / 100.0  # Convert cents to base currency
            payment_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': odoo_invoice.partner_id.id,
                'amount': payment_amount,  # Set the payment amount
                'currency_id': odoo_invoice.currency_id.id,
                'payment_date': payment_date,  # Set the payment date
                'journal_id': self.env['account.journal'].search([('type', '=', 'bank')], limit=1).id,
                'communication': odoo_invoice.name,
                # 'invoice_ids': [(6, 0, [odoo_invoice.id])],  # Link the invoice
            }
            try:
                # Register the payment with proper context
                payment_register = self.env['account.payment.register'].with_context(
                    active_model='account.move',
                    active_ids=odoo_invoice.id
                ).create(payment_vals)

                # Create and post the payment
                payment_register.action_create_payments()

                _logger.info(f"Registered and reconciled payment for invoice {odoo_invoice.name}: {payment_vals}")
            except Exception as e:
                _logger.error(f"Failed to register payment for invoice {odoo_invoice.name}: {e}")

    def _get_or_create_partner(self, invoice):
        """Fetch or create a partner based on Chargebee invoice data."""
        billing_address = getattr(invoice, 'billing_address', None)
        full_name = f"{getattr(billing_address, 'first_name', '')} {getattr(billing_address, 'last_name', '')}".strip()
        partner = self.env['res.partner'].search([('name', '=', full_name)], limit=1)

        if not partner:
            partner = self.env['res.partner'].create({
                'name': full_name,
                'phone': getattr(billing_address, 'phone', ''),
                'street': getattr(billing_address, 'street', ''),
                'city': getattr(billing_address, 'city', ''),
                'zip': getattr(billing_address, 'zip', ''),
                'country_id': self.env['res.country'].search([('name', '=', getattr(billing_address, 'country', ''))],
                                                             limit=1).id,
            })
        return partner