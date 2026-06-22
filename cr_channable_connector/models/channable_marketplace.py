# -*- coding: utf-8 -*-
# Part of Creyox Technologies
import logging
import requests
import uuid

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)



class ChannableMarketplace(models.Model):
    _name = 'channable.marketplace'
    _description = 'Channable Marketplace'

    name = fields.Char(string='Marketplace Name', required=True)
    order_configuration_id = fields.Char(
        string='Order Configuration ID', required=True,
        help='Market identifier in Channable'
    )
    project_id = fields.Many2one(
        'channable.project', string='Project',
        required=True, ondelete='cascade'
    )
    active = fields.Boolean(string='Active', default=True)

    # ── Assignments & Logistics ──────────────────────────────────────────────
    assign_error_user_id = fields.Many2one(
        'res.users', string='Assign errors to this user', required=True
    )
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', required=True)
    carrier_id = fields.Many2one('delivery.carrier', string='Default Carrier')

    # ── Accounting & Sales ───────────────────────────────────────────────────
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True)
    # account.payment.method is the correct model in Odoo 16+
    payment_journal_id = fields.Many2one(
        'account.journal', string='Payment Journal',
        domain=[('type', 'in', ['bank', 'cash'])],
        help='Journal used for automatic payment registration on confirmed orders'
    )
    default_fiscal_position_id = fields.Many2one(
        'account.fiscal.position', string='Default Fiscal Position'
    )
    intra_community_fiscal_position_id = fields.Many2one(
        'account.fiscal.position', string='Fiscal Position for Intra-Community Orders'
    )
    team_id = fields.Many2one('crm.team', string='Sales Team')
    language_id = fields.Many2one('res.lang', string='Language')
    tag_ids = fields.Many2many('res.partner.category', string='Tags')
    default_partner_vat = fields.Char(string='Default Partner VAT Number')

    # ── Synchronisation Configuration ────────────────────────────────────────
    sync_product_field = fields.Selection([
        ('default_code', 'Internal Reference'),
        ('barcode', 'Barcode'),
    ], string='Synchronisation Product Field', default='default_code', required=True)

    valid_states = fields.Char(
        string='Valid States',
        help='Comma-separated statuses to filter when importing orders (e.g. shipped, not_shipped)'
    )
    status_not_shipped = fields.Boolean(string='Not Shipped', default=True)
    status_shipped = fields.Boolean(string='Shipped')
    status_waiting = fields.Boolean(string='Waiting')
    status_pending_shipment = fields.Boolean(string='Pending Shipment')
    status_pending_cancellation = fields.Boolean(string='Pending Cancellation')
    status_cancelled = fields.Boolean(string='Cancelled')
    notify_shipped_auto = fields.Boolean(string='Notify as Shipped Automatically')
    saving_attachments = fields.Selection([
        ('url', 'Save URL'),
        ('download', 'Download to Database'),
    ], string='Saving Attachments', default='url')

    auto_validate_quotations = fields.Boolean(string='Auto Validate Quotations')
    auto_validate_orders = fields.Boolean(string='Auto Validate Orders')
    auto_validate_invoices = fields.Boolean(
        string='Auto Validate Invoices on Order Confirmation'
    )
    difference_threshold = fields.Float(
        string='Allow Difference of Totals to Auto Validate the Quotation'
    )

    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency_id')
    orders_pending_validation_count = fields.Integer(compute='_compute_dashboard_stats')
    orders_pending_validation_amount = fields.Monetary(
        compute='_compute_dashboard_stats', string="Amount Pending Validation", currency_field='currency_id'
    )
    orders_pending_shipment_count = fields.Integer(compute='_compute_dashboard_stats')
    orders_pending_shipment_amount = fields.Monetary(
        compute='_compute_dashboard_stats', string="Amount Pending Shipment", currency_field='currency_id'
    )
    kanban_dashboard_graph = fields.Text(compute='_compute_kanban_dashboard_graph')
    color = fields.Integer(string='Color Index', default=0)
    feed_token = fields.Char(string='Feed Token', copy=False, readonly=True)
    feed_url = fields.Char(string='Product Feed URL', compute='_compute_feed_url')
    attribute_mapping_ids = fields.One2many(
        'channable.attribute.mapping', 'marketplace_id',
        string='Attribute Mappings'
    )
    shipping_mapping_ids = fields.One2many(
        'channable.shipping.mapping', 'marketplace_id',
        string='Shipping Mappings'
    )
    dark_mode = fields.Boolean(string='Dashboard Dark Mode', default=False)
    sync_in_progress = fields.Boolean(string='Sync In Progress', default=False)
    sync_total_orders = fields.Integer(string='Sync Total Orders', default=0)
    sync_processed_orders = fields.Integer(string='Sync Processed Orders', default=0)
    sync_progress_percentage = fields.Integer(
        string='Sync Progress Percentage',
        compute='_compute_sync_progress_percentage'
    )
    sync_log_ids = fields.One2many('channable.sync.log', 'marketplace_id', string='Sync Logs')
    sync_log_count = fields.Integer(string='Sync Log Count', compute='_compute_sync_log_count')
    last_sync_date = fields.Datetime(string='Last Sync Date')
    last_sync_duration = fields.Char(string='Last Sync Duration')
    last_sync_orders_count = fields.Integer(string='Last Sync Orders Count')
    last_sync_status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('partial', 'Partial')
    ], string='Last Sync Status')

    def _compute_sync_log_count(self):
        if self.ids:
            self.env.cr.execute(
                "SELECT marketplace_id, COUNT(*) FROM channable_sync_log WHERE marketplace_id IN %s GROUP BY marketplace_id",
                (tuple(self.ids),)
            )
            counts = dict(self.env.cr.fetchall())
        else:
            counts = {}
        for mp in self:
            mp.sync_log_count = counts.get(mp.id, 0)

    @api.depends('sync_total_orders', 'sync_processed_orders')
    def _compute_sync_progress_percentage(self):
        for mp in self:
            if mp.sync_total_orders > 0:
                mp.sync_progress_percentage = int((mp.sync_processed_orders / mp.sync_total_orders) * 100)
            else:
                mp.sync_progress_percentage = 0

    _sql_constraints = [
        ('marketplace_identifier_name_uniq', 'unique(order_configuration_id, name)',
         'There can only be one market with the same identifier and name!')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('feed_token'):
                vals['feed_token'] = str(uuid.uuid4())
        return super(ChannableMarketplace, self).create(vals_list)

    def _compute_feed_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for mp in self:
            if not mp.feed_token:
                mp.sudo().write({'feed_token': str(uuid.uuid4())})
            mp.feed_url = f"{base_url}/channable/feed/{mp.feed_token}"

    @api.depends('pricelist_id')
    def _compute_currency_id(self):
        for mp in self:
            mp.currency_id = mp.pricelist_id.currency_id or self.env.company.currency_id

    def _compute_dashboard_stats(self):
        for mp in self:
            # 1. Orders pending validation (draft/sent status)
            validation_orders = self.env['sale.order'].search([
                ('channable_marketplace_id', '=', mp.id),
                ('state', 'in', ['draft', 'sent']),
            ])
            mp.orders_pending_validation_count = len(validation_orders)
            mp.orders_pending_validation_amount = sum(validation_orders.mapped('amount_total'))

            # 2. Orders pending to be shipped
            pending_pickings = self.env['stock.picking'].search([
                ('sale_id.channable_marketplace_id', '=', mp.id),
                ('state', 'not in', ['done', 'cancel']),
                ('picking_type_code', '=', 'outgoing'),
            ])
            pending_ship_orders = pending_pickings.mapped('sale_id')
            mp.orders_pending_shipment_count = len(pending_ship_orders)
            mp.orders_pending_shipment_amount = sum(pending_ship_orders.mapped('amount_total'))

    def _compute_kanban_dashboard_graph(self):
        import json
        import datetime
        from datetime import timedelta
        from odoo.tools.misc import format_date

        for mp in self:
            today = fields.Date.today()
            # 7 days graph
            days = [today - timedelta(days=i) for i in range(6, -1, -1)]
            
            orders = self.env['sale.order'].search([
                ('channable_marketplace_id', '=', mp.id),
                ('state', 'in', ['sale', 'done']),
                ('date_order', '>=', fields.Datetime.to_string(datetime.datetime.combine(days[0], datetime.time.min))),
            ])
            
            daily_amounts = {day: 0.0 for day in days}
            for order in orders:
                order_date = order.date_order.date()
                if order_date in daily_amounts:
                    daily_amounts[order_date] += order.amount_total
            
            values = []
            for day in days:
                values.append({
                    'x': format_date(self.env, day, date_format='d LLL'),
                    'y': daily_amounts[day],
                })
            
            all_zero = all(v['y'] == 0 for v in values)
            if all_zero:
                # Provide standard wavy sample data so the dashboard looks great immediately
                sample_ys = [120, 80, 240, 150, 420, 260, 510]
                variance_factor = (len(mp.name or '') % 3 + 1) * 0.7
                for idx, val in enumerate(values):
                    val['y'] = round(sample_ys[idx] * variance_factor, 2)
            
            graph_data = [{
                'values': values,
                'title': '',
                'key': _('Sales'),
                'is_sample_data': all_zero,
                'area': True,
            }]
            mp.kanban_dashboard_graph = json.dumps(graph_data)

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_toggle_dark_mode(self):
        self.ensure_one()
        self.dark_mode = not self.dark_mode
        return False

    def action_push_product_stock(self):
        self.ensure_one()
        connection = self.project_id.connection_id
        if not connection:
            raise UserError(_("No connection configured for this project/marketplace."))

        sync_field = self.sync_product_field
        # Find all active products that have a value in the configured sync field
        products = self.env['product.product'].search([
            (sync_field, '!=', False),
            (sync_field, '!=', ''),
        ])

        if not products:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Push Product Stock'),
                    'message': _('No products found with a valid %s.') % (self._fields['sync_product_field'].string),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        url_base = (
            f'https://api.channable.com/v1/companies/{connection.company_id_num}'
            f'/projects/{self.project_id.channable_identifier}'
        )
        url = f'{url_base}/offers'
        headers = {
            'Authorization': f'Bearer {connection.api_token.strip()}',
            'Content-Type': 'application/json',
        }

        offers = []
        for product in products:
            # Retrieve quantity available in the context of the marketplace's warehouse
            stock_qty = product.with_context(warehouse=self.warehouse_id.id).qty_available
            channable_product_id = getattr(product, sync_field)
            if not channable_product_id:
                continue
            offers.append({
                'id': str(channable_product_id),
                'stock': int(stock_qty) if stock_qty > 0 else 0
            })

        if not offers:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Push Product Stock'),
                    'message': _('No products found to sync.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Send to Channable in chunks of 100 to optimize payload size and avoid timeouts
        chunk_size = 100
        total_pushed = 0
        try:
            for i in range(0, len(offers), chunk_size):
                chunk = offers[i:i + chunk_size]
                resp = requests.post(url, headers=headers, json=chunk, timeout=30)
                resp.raise_for_status()
                total_pushed += len(chunk)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Push Product Stock Successful'),
                    'message': _('Successfully pushed stock for %d products to Channable.') % total_pushed,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            # Log the error in channable.sync.error
            self.env['channable.sync.error'].create({
                'name': _('Push Product Stock Failed'),
                'marketplace_id': self.id,
                'action_attempted': 'push_stock',
                'detailed_description': str(e),
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Push Product Stock Failed'),
                    'message': _('Error pushing product stock to Channable: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_sync_orders(self):
        self.ensure_one()
        return {
            'name': _('Import Channable orders - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'channable.sync.orders.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_marketplace_id': self.id},
        }

    @api.model
    def action_sync_orders_cron(self):
        """Cron: auto-import orders for all active marketplaces."""
        for marketplace in self.search([('active', '=', True)]):
            try:
                wizard = self.env['channable.sync.orders.wizard'].with_context(
                    sync_synchronously=True,
                    default_marketplace_id=marketplace.id
                ).create({
                    'marketplace_id': marketplace.id,
                })
                wizard.action_import_orders()
            except Exception:
                _logger.exception("Cron auto-import failed for marketplace '%s'", marketplace.name)

    def action_sync_orders_shipment(self):
        """Sync shipments for all pending orders in this marketplace."""
        self.ensure_one()
        orders = self.env['sale.order'].search([
            ('channable_marketplace_id', '=', self.id),
            ('state', 'in', ['sale', 'done']),
            ('channable_status', 'not in', ['shipped', 'canceled', 'cancelled', 'manual']),
            ('picking_ids.state', '=', 'done'),
            ('picking_ids.channable_sync_status', '=', 'pending'),
        ])
        if orders:
            orders.action_channable_notify_shipped()

    def action_view_orders(self):
        self.ensure_one()
        return {
            'name': _('Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('channable_marketplace_id', '=', self.id)],
            'context': {'default_channable_marketplace_id': self.id},
        }

    def action_view_errors(self):
        self.ensure_one()
        return {
            'name': _('Sync Errors'),
            'type': 'ir.actions.act_window',
            'res_model': 'channable.sync.error',
            'view_mode': 'list,form',
            'domain': [('marketplace_id', '=', self.id)],
            'context': {'default_marketplace_id': self.id},
        }

    def action_view_pending_validation(self):
        self.ensure_one()
        return {
            'name': _('Pending Validation'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [
                ('channable_marketplace_id', '=', self.id),
                ('state', 'in', ['draft', 'sent']),
            ],
            'context': {'default_channable_marketplace_id': self.id},
        }

    def action_view_pending_delivery(self):
        self.ensure_one()
        return {
            'name': _('Pending Delivery'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [
                ('sale_id.channable_marketplace_id', '=', self.id),
                ('state', 'not in', ['done', 'cancel']),
                ('picking_type_code', '=', 'outgoing'),
            ],
        }

    def action_view_sync_logs(self):
        self.ensure_one()
        return {
            'name': _('Sync Logs'),
            'type': 'ir.actions.act_window',
            'res_model': 'channable.sync.log',
            'view_mode': 'list,form',
            'domain': [('marketplace_id', '=', self.id)],
            'context': {'default_marketplace_id': self.id},
        }
