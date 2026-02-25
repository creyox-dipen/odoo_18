# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models, fields, api, http, _
import chargebee

class ChargebeeConfiguration(models.Model):
    _name = "chargebee.configuration"
    _description = "Chargebee API Configuration"
    _rec_name = "site_name"

    reference = fields.Char(string='Sequence', required=True, readonly=True, default='New')
    api_key = fields.Char(string="Api Key")
    site_name = fields.Char(string="Site Name")
    is_active_field_for_customers = fields.Boolean(string="Auto Import", default=False)

    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company, readonly=True
    )
    cr_data_logs_ids = fields.One2many(
        "cr.data.processing.log", "cr_configuration_id", string="Logs"
    )
    # Computed fields for specific logs based on cr_context
    currency_logs_ids = fields.One2many(
        'cr.data.processing.log', compute='_compute_currency_logs', string="Currency Logs"
    )
    item_family_logs_ids = fields.One2many(
        'cr.data.processing.log', compute='_compute_item_family_logs', string="Item Family Logs"
    )
    item_logs_ids = fields.One2many(
        'cr.data.processing.log', compute='_compute_item_logs', string="Item Logs"
    )
    customer_logs_ids = fields.One2many(
        'cr.data.processing.log', compute='_compute_customer_logs', string="Customer Logs"
    )
    tax_logs_ids = fields.One2many(
        'cr.data.processing.log', compute='_compute_tax_logs', string="Tax Logs"
    )
    invoice_logs_ids = fields.One2many(
        'cr.data.processing.log', compute='_compute_invoice_logs', string="Invoice Logs"
    )

    @api.depends('cr_data_logs_ids')
    def _compute_currency_logs(self):
        for record in self:
            record.currency_logs_ids = record.cr_data_logs_ids.filtered(lambda log: log.cr_context == 'currencies')

    @api.depends('cr_data_logs_ids')
    def _compute_invoice_logs(self):
        for record in self:
            record.invoice_logs_ids = record.cr_data_logs_ids.filtered(lambda log: log.cr_context == 'invoices')

    @api.depends('cr_data_logs_ids')
    def _compute_item_family_logs(self):
        for record in self:
            record.item_family_logs_ids = record.cr_data_logs_ids.filtered(lambda log: log.cr_context == 'itemsfamily')

    @api.depends('cr_data_logs_ids')
    def _compute_item_logs(self):
        for record in self:
            record.item_logs_ids = record.cr_data_logs_ids.filtered(lambda log: log.cr_context == 'items')

    @api.depends('cr_data_logs_ids')
    def _compute_customer_logs(self):
        for record in self:
            record.customer_logs_ids = record.cr_data_logs_ids.filtered(lambda log: log.cr_context == 'customers')

    @api.depends('cr_data_logs_ids')
    def _compute_tax_logs(self):
        for record in self:
            record.tax_logs_ids = record.cr_data_logs_ids.filtered(lambda log: log.cr_context == 'taxes')


    def toggle_scheduled_action(self):
        """Activate or deactivate the scheduled action based on active_field"""
        cron = self.env.ref('cr_chargebee_odoo_connector.ir_cron_auto_update_customers', raise_if_not_found=False)
        if cron:
            # Activate if any record has active_field set to True
            if self.search_count([('is_active_field_for_customers', '=', True)]):
                cron.active = True
            else:
                cron.active = False

    def create(self, vals):
        vals['reference'] = self.env['ir.sequence'].next_by_code('chargebee.configuration') or 'New'
        record = super().create(vals)
        if 'is_active_field_for_customers' in vals:
            self.toggle_scheduled_action()
        return record

    def write(self, vals):
        result = super().write(vals)
        if 'is_active_field_for_customers' in vals:
            self.toggle_scheduled_action()
        return result

    def action_open_sync_wizard(self):
        """Open the wizard or list view depending on records."""
        return {
                'type': 'ir.actions.act_window',
                'name': _('Sync Chargebee Item Families'),
                'res_model': 'chargebee.item.family.sync.wizard',
                'view_mode': 'form',
                'target': 'new',
            }

    def sync_chargebee_customers_(self):
        self.env['res.partner'].sync_chargebee_customers()
        """Open the wizard or list view depending on records."""
        return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chargebee Customers',
                    'message': f"Successfully Synced",
                    'type': 'success',
                    'sticky': False,
                },
            }

    def sync_taxes_from_chargebee_(self):
        self.env['account.tax'].sync_taxes_from_chargebee()
        """Open the wizard or list view depending on records."""
        return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chargebee Tax',
                    'message': f"Successfully Synced",
                    'type': 'success',
                    'sticky': False,
                },
            }

    def sync_chargebee_currencies_(self):
        self.env['res.currency'].sync_chargebee_currencies()
        """Open the wizard or list view depending on records."""
        return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chargebee Currencies',
                    'message': f"Successfully Synced",
                    'type': 'success',
                    'sticky': False,
                },
            }

    def action_sync_chargebee_credit_note(self):
        """Perform the sync and close the wizard."""
        self.env['account.move'].action_sync_credit_notes()
        return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chargebee Credit Notes',
                    'message': f"Successfully Synced",
                    'type': 'success',
                    'sticky': False,
                },
            }

    def action_sync_chargebee_subscriptions(self):
        """Perform the sync and close the wizard."""
        self.env['chargebee.subscription'].action_sync_subscriptions()
        return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chargebee Subscriptions',
                    'message': f"Successfully Synced",
                    'type': 'success',
                    'sticky': False,
                },
            }

    def action_sync_chargebee_items(self):
        self.env['product.template'].sync_items_from_chargebee()
        return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chargebee Items',
                    'message': f"Successfully Synced",
                    'type': 'success',
                    'sticky': False,
                },
            }

    def action_sync_chargebee_invoice_for_account_move(self):
        """Perform the sync and close the wizard."""
        self.env['account.move'].action_sync_account_invoices()
        return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chargebee Account Invoices',
                    'message': f"Successfully Synced",
                    'type': 'success',
                    'sticky': False,
                },
            }

    def test_connection(self):
        """Test the Chargebee API connection."""
        self.ensure_one()
        try:
            # Configure Chargebee with provided API key and site URL
            chargebee.configure(self.api_key, self.site_name)
            # Test API by listing customers (or any simple API call)
            chargebee.Customer.list({"limit": 1})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Successful',
                    'message': 'The API key and site URL are valid.',
                    'type': 'success',
                    'sticky': False,
                },
            }
        except chargebee.APIError as e:
            # Extracting error details from Chargebee APIError object
            error_message = e.json_obj.get('message', 'An unknown error occurred')
            http_code = e.http_code

            # Handle API error gracefully
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Failed',
                    'message': f"Error {http_code}: {error_message}",
                    'type': 'danger',
                    'sticky': False,
                },
            }

        except Exception as e:
            # Handle other unexpected errors gracefully
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Unexpected Error',
                    'message': str(e),
                    'type': 'danger',
                    'sticky': False,
                },
            }
