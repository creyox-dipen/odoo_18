# -*- coding: utf-8 -*-
# Part of Creyox Technologies
import datetime
import logging
import requests
import traceback

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class ChannableSyncOrdersWizard(models.TransientModel):
    _name = 'channable.sync.orders.wizard'
    _description = 'Channable Sync Orders Wizard'

    marketplace_id = fields.Many2one('channable.marketplace', string='Marketplace', required=True)
    date_start = fields.Datetime(
        string='Date From',
        default=lambda self: fields.Datetime.now() - datetime.timedelta(days=1)
    )
    date_end = fields.Datetime(string='Date To', default=fields.Datetime.now)
    import_by_id = fields.Boolean(string='Import Orders by ID')
    order_ids_str = fields.Char(
        string='Order IDs',
        help='Comma-separated Channable Order Identifiers'
    )
    
    # Boolean checkboxes for multi-select status filtering (avoids security rules limitations)
    status_not_shipped = fields.Boolean(string='Not Shipped')
    status_shipped = fields.Boolean(string='Shipped')
    status_waiting = fields.Boolean(string='Waiting')
    status_pending_shipment = fields.Boolean(string='Pending Shipment')
    status_pending_cancellation = fields.Boolean(string='Pending Cancellation')
    status_cancelled = fields.Boolean(string='Cancelled')

    @api.model
    def default_get(self, fields_list):
        res = super(ChannableSyncOrdersWizard, self).default_get(fields_list)
        marketplace_id = res.get('marketplace_id') or self._context.get('default_marketplace_id')
        if marketplace_id:
            marketplace = self.env['channable.marketplace'].browse(marketplace_id)
            # If any status checkbox is True on the marketplace, copy them directly
            status_fields = ['status_not_shipped', 'status_shipped', 'status_waiting', 
                             'status_pending_shipment', 'status_pending_cancellation', 'status_cancelled']
            has_checked = any(getattr(marketplace, f) for f in status_fields)
            if has_checked:
                for field_name in status_fields:
                    if field_name in fields_list or field_name in self._fields:
                        res[field_name] = getattr(marketplace, field_name)
            elif marketplace.valid_states:
                # Fallback to the old comma-separated field
                raw_states = [s.strip() for s in marketplace.valid_states.split(',') if s.strip()]
                for state in raw_states:
                    api_state = 'cancelled' if state == 'canceled' else state
                    field_name = f'status_{api_state}'
                    if field_name in fields_list or field_name in self._fields:
                        res[field_name] = True
        return res


    # ── Internal helpers ──────────────────────────────────────────────────────

    def _log_error(self, name, action, description, order_id=False):
        self.env['channable.sync.error'].create({
            'name': name,
            'marketplace_id': self.marketplace_id.id,
            'order_id': order_id or False,
            'action_attempted': action,
            'detailed_description': str(description),
        })

    def _get_or_create_partner(self, billing_data, marketplace, country_cache=None, state_cache=None, partner_cache=None):
        """
        Find an existing res.partner by e-mail or create a new one.
        Returns a res.partner record (invoice / billing address).
        """
        if country_cache is None:
            country_cache = {}
        if state_cache is None:
            state_cache = {}
        if partner_cache is None:
            partner_cache = {}

        Partner = self.env['res.partner']
        email = (billing_data.get('email') or '').strip().lower()

        # Check in-memory cache first
        if email and email in partner_cache:
            return partner_cache[email]

        # ── Search existing partner ──────────────────────────────────────────
        partner = False
        if email:
            # Prefer a company-contact or individual with this e-mail
            partner = Partner.search([
                ('email', '=ilike', email),
                ('type', 'in', ['contact', False]),
            ], limit=1)

        if not partner:
            # ── Resolve country & state ──────────────────────────────────────
            country = False
            state = False
            country_code = billing_data.get('country_code') or billing_data.get('country', '')
            if country_code:
                country_code_upper = country_code[:2].upper()
                if country_code_upper in country_cache:
                    country = country_cache[country_code_upper]
                else:
                    country = self.env['res.country'].search(
                        [('code', '=ilike', country_code[:2])], limit=1
                    )
                    if country:
                        country_cache[country_code_upper] = country

            state_code = billing_data.get('state_code') or billing_data.get('state', '')
            if country and state_code:
                state_code_upper = state_code.strip().upper()
                state_key = (country.id, state_code_upper)
                if state_key in state_cache:
                    state = state_cache[state_key]
                else:
                    state = self.env['res.country.state'].search([
                        ('country_id', '=', country.id),
                        ('code', '=ilike', state_code),
                    ], limit=1)
                    if state:
                        state_cache[state_key] = state

            fname = billing_data.get('first_name', '').strip()
            lname = billing_data.get('last_name', '').strip()
            full_name = f'{fname} {lname}'.strip() or 'Channable Customer'
            company_name = billing_data.get('company', '').strip()

            partner_vals = {
                'name': full_name,
                'email': email,
                'phone': billing_data.get('phone', ''),
                'street': billing_data.get('street', ''),
                'street2': billing_data.get('street2', ''),
                'city': billing_data.get('city', ''),
                'zip': billing_data.get('zip_code', ''),
                'vat': billing_data.get('vat') or marketplace.default_partner_vat or False,
                'lang': (
                    marketplace.language_id.code
                    if marketplace.language_id
                    else self.env.user.lang
                ),
                'customer_rank': 1,
            }
            if country:
                partner_vals['country_id'] = country.id
            if state:
                partner_vals['state_id'] = state.id
            if company_name:
                # Make the partner a contact of a company
                partner_vals['company_name'] = company_name
            if marketplace.tag_ids:
                partner_vals['category_id'] = [(6, 0, marketplace.tag_ids.ids)]

            partner = Partner.with_context(
                mail_create_nosubscribe=True, mail_create_nolog=True, tracking_disable=True
            ).create(partner_vals)

        # Save to cache
        if email and partner:
            partner_cache[email] = partner

        return partner

    def _get_or_create_shipping_partner(self, shipping_data, invoice_partner, marketplace, country_cache=None, state_cache=None, shipping_partner_cache=None):
        """
        Return a shipping address partner.
        - If the shipping address matches the billing address, reuse invoice_partner.
        - Otherwise create (or find) a child 'delivery' address linked to invoice_partner.
        """
        if country_cache is None:
            country_cache = {}
        if state_cache is None:
            state_cache = {}
        if shipping_partner_cache is None:
            shipping_partner_cache = {}

        Partner = self.env['res.partner']

        ship_street = (shipping_data.get('street') or '').strip()
        ship_city = (shipping_data.get('city') or '').strip()
        ship_zip = (shipping_data.get('zip_code') or '').strip()

        # Quick equality check
        if (ship_street == (invoice_partner.street or '').strip()
                and ship_city == (invoice_partner.city or '').strip()
                and ship_zip == (invoice_partner.zip or '').strip()):
            return invoice_partner

        # Check in-memory cache first
        cache_key = (invoice_partner.id, ship_street, ship_city, ship_zip)
        if cache_key in shipping_partner_cache:
            return shipping_partner_cache[cache_key]

        # Resolve country/state for shipping
        country = False
        state = False
        country_code = shipping_data.get('country_code') or shipping_data.get('country', '')
        if country_code:
            country_code_upper = country_code[:2].upper()
            if country_code_upper in country_cache:
                country = country_cache[country_code_upper]
            else:
                country = self.env['res.country'].search(
                    [('code', '=ilike', country_code[:2])], limit=1
                )
                if country:
                    country_cache[country_code_upper] = country

        state_code = shipping_data.get('state_code') or shipping_data.get('state', '')
        if country and state_code:
            state_code_upper = state_code.strip().upper()
            state_key = (country.id, state_code_upper)
            if state_key in state_cache:
                state = state_cache[state_key]
            else:
                state = self.env['res.country.state'].search([
                    ('country_id', '=', country.id),
                    ('code', '=ilike', state_code),
                ], limit=1)
                if state:
                    state_cache[state_key] = state

        fname = shipping_data.get('first_name', '').strip()
        lname = shipping_data.get('last_name', '').strip()
        ship_name = f'{fname} {lname}'.strip() or invoice_partner.name

        # Search for an existing delivery child under this partner
        domain = [
            ('parent_id', '=', invoice_partner.id),
            ('type', '=', 'delivery'),
            ('street', '=', ship_street),
            ('city', '=', ship_city),
            ('zip', '=', ship_zip),
        ]
        shipping_partner = Partner.search(domain, limit=1)
        if not shipping_partner:
            ship_vals = {
                'name': ship_name,
                'type': 'delivery',
                'parent_id': invoice_partner.id,
                'street': ship_street,
                'street2': shipping_data.get('street2', ''),
                'city': ship_city,
                'zip': ship_zip,
                'phone': shipping_data.get('phone', '') or invoice_partner.phone,
                'email': invoice_partner.email,
            }
            if country:
                ship_vals['country_id'] = country.id
            if state:
                ship_vals['state_id'] = state.id
            shipping_partner = Partner.with_context(
                mail_create_nosubscribe=True, mail_create_nolog=True, tracking_disable=True
            ).create(ship_vals)

        # Cache the result
        shipping_partner_cache[cache_key] = shipping_partner

        return shipping_partner

    # ── Main action ───────────────────────────────────────────────────────────

    def action_import_orders(self):
        self.ensure_one()
        _logger.warning("[Channable] action_import_orders CALLED - import_by_id=%s, order_ids_str=%s", self.import_by_id, self.order_ids_str)
        
        # If running synchronously (e.g. cron or when explicitly requested)
        if self._context.get('sync_synchronously'):
            self._execute_import(self.marketplace_id)
            return {'type': 'ir.actions.act_window_close'}
            
        # Otherwise, run in a background thread to prevent UI blocking
        import threading
        
        wizard_vals = {
            'marketplace_id': self.marketplace_id.id,
            'import_by_id': self.import_by_id,
            'order_ids_str': self.order_ids_str,
            'date_start': self.date_start,
            'date_end': self.date_end,
            'status_not_shipped': self.status_not_shipped,
            'status_shipped': self.status_shipped,
            'status_waiting': self.status_waiting,
            'status_pending_shipment': self.status_pending_shipment,
            'status_pending_cancellation': self.status_pending_cancellation,
            'status_cancelled': self.status_cancelled,
        }
        
        # Mark sync as in progress in main thread so UI shows it immediately
        self.marketplace_id.write({
            'sync_in_progress': True,
            'sync_total_orders': 0,
            'sync_processed_orders': 0,
        })
        self.env.cr.commit()

        # We start a thread using Odoo registry
        registry = self.env.registry
        user_id = self.env.user.id
        ctx = dict(self.env.context)
        
        def run_sync():
            with registry.cursor() as cr:
                env = api.Environment(cr, user_id, ctx)
                try:
                    marketplace_new = env['channable.marketplace'].browse(wizard_vals['marketplace_id'])
                    # Create a temporary wizard in the new cursor environment
                    wizard_new = env['channable.sync.orders.wizard'].with_context(default_marketplace_id=False).create(wizard_vals)
                    wizard_new._execute_import(marketplace_new)
                except Exception as threaded_err:
                    _logger.exception("Background order sync failed: %s", str(threaded_err))

        t = threading.Thread(target=run_sync)
        t.daemon = True
        t.start()
        
        # Return a non-blocking toast action that closes the wizard and reloads the view
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Order Sync Started'),
                'message': _('Importing orders in the background. You can track progress on the Marketplace form view.'),
                'type': 'info',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
            }
        }

    def _execute_import(self, marketplace):
        start_time = datetime.datetime.now()
        
        orders_count = 0
        total_synced = 0
        total_skipped = 0
        status = 'success'
        notes = ''

        try:
            # Initialize in-memory caches to drastically reduce database round-trips
            country_cache = {c.code.upper(): c for c in self.env['res.country'].search([]) if c.code}
            state_cache = {(s.country_id.id, s.code.upper()): s for s in self.env['res.country.state'].search([]) if s.code and s.country_id}
            partner_cache = {}
            shipping_partner_cache = {}
            connection = marketplace.project_id.connection_id
            if not connection:
                raise Exception(_("No connection configured for this project/marketplace."))

            headers = {
                'Authorization': f'Bearer {connection.api_token.strip()}',
                'Content-Type': 'application/json',
            }
            # Use v2 endpoint – the v1 endpoint is deprecated and returns 404
            # when status + date range parameters combined.
            url = (
                f'https://api.channable.com/v2/companies/{connection.company_id_num}'
                f'/projects/{marketplace.project_id.channable_identifier}/orders'
            )

            params = {}
            if self.import_by_id and self.order_ids_str:
                params['order_ids'] = self.order_ids_str.strip()
            elif not self.import_by_id:
                params['start_date'] = self.date_start.strftime('%Y-%m-%dT%H:%M:%S')
                params['end_date'] = self.date_end.strftime('%Y-%m-%dT%H:%M:%S')

            statuses = []
            if not self.import_by_id:
                if self.status_not_shipped:
                    statuses.append('not_shipped')
                if self.status_shipped:
                    statuses.append('shipped')
                if self.status_waiting:
                    statuses.append('waiting')
                if self.status_pending_shipment:
                    statuses.append('pending_shipment')
                if self.status_pending_cancellation:
                    statuses.append('pending_cancellation')
                if self.status_cancelled:
                    statuses.append('cancelled')
                
            orders_data = []
            if self.import_by_id and self.order_ids_str:
                order_ids = [oid.strip() for oid in self.order_ids_str.split(',') if oid.strip()]
                _logger.warning("[Channable] Parsed IDs to fetch: %s", order_ids)
                for oid in order_ids:
                    single_url = f"{url}/{oid}"
                    _logger.warning("[Channable] Fetching single order by ID: %s", single_url)
                    response = requests.get(single_url, headers=headers, timeout=30)
                    _logger.warning("[Channable] Fetch single order ID %s response status: %s", oid, response.status_code)
                    if response.status_code == 404:
                        _logger.warning("[Channable] Order ID %s not found in Channable (404)", oid)
                        continue
                    response.raise_for_status()
                    order_payload = response.json()
                    _logger.warning("[Channable] Fetch single order ID %s payload: %s", oid, order_payload)
                    order_obj = order_payload.get('order') or order_payload
                    if order_obj and order_obj.get('id'):
                        orders_data.append(order_obj)
                            
            elif not self.import_by_id and statuses:
                seen_order_ids = set()
                for status_filter in statuses:
                    offset = 0
                    limit = 100
                    while True:
                        req_params = params.copy()
                        req_params['status'] = status_filter
                        req_params['offset'] = offset
                        req_params['limit'] = limit
                        response = requests.get(url, headers=headers, params=req_params, timeout=30)
                        response.raise_for_status()
                        data = response.json()
                        page_orders = data.get('orders', [])
                        _logger.warning(
                            "[Channable] Raw API response | status=%s | offset=%d | URL: %s\nFetched %d orders",
                            status_filter, offset, response.url, len(page_orders)
                        )
                        for o in page_orders:
                            o_id = o.get('id')
                            if o_id and o_id not in seen_order_ids:
                                seen_order_ids.add(o_id)
                                orders_data.append(o)
                        if len(page_orders) < limit:
                            break
                        offset += limit
            else:
                offset = 0
                limit = 100
                while True:
                    req_params = params.copy()
                    req_params['offset'] = offset
                    req_params['limit'] = limit
                    response = requests.get(url, headers=headers, params=req_params, timeout=30)
                    response.raise_for_status()
                    data = response.json()
                    page_orders = data.get('orders', [])
                    _logger.warning(
                        "[Channable] Raw API response | offset=%d | URL: %s\nFetched %d orders",
                        offset, response.url, len(page_orders)
                    )
                    for o in page_orders:
                        orders_data.append(o)
                    if len(page_orders) < limit:
                        break
                    offset += limit

            orders_count = len(orders_data)
            
            if not orders_data:
                notes = _("No orders fetched from the API.")
                return

            marketplace.write({
                'sync_in_progress': True,
                'sync_total_orders': orders_count,
                'sync_processed_orders': 0,
            })
            self.env.cr.commit()

            # Batch orders
            batch_size = 50
            for i in range(0, orders_count, batch_size):
                batch = orders_data[i:i + batch_size]
                try:
                    batch_result = self._process_order_batch(
                        batch,
                        marketplace,
                        country_cache=country_cache,
                        state_cache=state_cache,
                        partner_cache=partner_cache,
                        shipping_partner_cache=shipping_partner_cache
                    )
                    total_synced += batch_result.get('synced', 0)
                    total_skipped += batch_result.get('skipped', 0)
                    # Commit progress after successfully processing the batch
                    marketplace.write({
                        'sync_processed_orders': min(i + batch_size, orders_count),
                    })
                    self.env.cr.commit()
                except Exception as batch_err:
                    self.env.cr.rollback()
                    _logger.exception("Error processing order batch starting at index %d: %s", i, str(batch_err))
                    # Update processed count anyway to move forward
                    try:
                        marketplace.write({
                            'sync_processed_orders': min(i + batch_size, orders_count),
                        })
                        self.env.cr.commit()
                    except Exception:
                        pass
            
            # Determine sync status
            attempted_new = orders_count - total_skipped
            if attempted_new > 0:
                if total_synced == attempted_new:
                    status = 'success'
                elif total_synced > 0:
                    status = 'partial'
                else:
                    status = 'failed'
            else:
                status = 'success'

            notes = _(
                "Successfully executed sync.\n"
                "Total orders fetched from API: %d\n"
                "New orders imported: %d\n"
                "Existing orders skipped: %d"
            ) % (orders_count, total_synced, total_skipped)

        except Exception as e:
            status = 'failed'
            notes = f"Sync failed with error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            _logger.exception("Error during _execute_import: %s", str(e))
            self._log_error('Sync Execution Error', 'sync_order', e)

        finally:
            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Write to channable.sync.log
            log_name = f"Sync - {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
            try:
                self.env['channable.sync.log'].create({
                    'name': log_name,
                    'marketplace_id': marketplace.id,
                    'start_datetime': start_time,
                    'end_datetime': end_time,
                    'duration': duration,
                    'orders_count': orders_count,
                    'synced_count': total_synced,
                    'status': status,
                    'notes': notes,
                })
            except Exception as log_err:
                _logger.error("Failed to create channable.sync.log: %s", str(log_err))

            # Update latest sync metrics on the marketplace
            try:
                marketplace.write({
                    'sync_in_progress': False,
                    'last_sync_date': start_time,
                    'last_sync_duration': f"{duration:.2f}s",
                    'last_sync_orders_count': total_synced,
                    'last_sync_status': status,
                })
                self.env.cr.commit()
            except Exception as mp_err:
                _logger.error("Failed to update marketplace sync statistics: %s", str(mp_err))

    def _process_order_batch(self, orders_data, marketplace, country_cache=None, state_cache=None, partner_cache=None, shipping_partner_cache=None):
        SaleOrder = self.env['sale.order']
        new_orders = self.env['sale.order']

        # ── Bulk Fetch Existing Orders ─────────────────────────────────────────
        _logger.warning("[Channable] Total orders fetched from API: %d", len(orders_data))
        if orders_data:
            _logger.warning("[Channable] First order raw payload:\n%s", orders_data[0])

        channable_ids = [str(o.get('id', '')) for o in orders_data if o.get('id')]
        _logger.debug("Found %d orders from Channable API", len(channable_ids))
        existing_channable_ids = set()
        if channable_ids:
            self.env.cr.execute(
                "SELECT channable_order_id FROM sale_order WHERE channable_order_id IN %s",
                (tuple(channable_ids),)
            )
            existing_channable_ids = {r[0] for r in self.env.cr.fetchall() if r[0]}
        _logger.debug("Existing orders in Odoo: %s", existing_channable_ids)

        # ── Bulk Fetch Existing Products ───────────────────────────────────────
        product_refs = []
        for o in orders_data:
            inner_data = o.get('data', {})
            for p in inner_data.get('products', []):
                ref = str(p.get('ean', '') if marketplace.sync_product_field == 'barcode' else p.get('id', ''))
                if ref:
                    product_refs.append(ref)
        product_refs = list(set(product_refs))

        product_dict = {}
        if product_refs:
            sync_field = marketplace.sync_product_field
            if sync_field in ['default_code', 'barcode']:
                self.env.cr.execute(
                    f"SELECT id, {sync_field} FROM product_product WHERE {sync_field} IN %s AND active = true",
                    (tuple(product_refs),)
                )
                product_rows = self.env.cr.fetchall()
                product_ids = [row[0] for row in product_rows]
                products = self.env['product.product'].browse(product_ids)
                product_dict = {getattr(p, sync_field): p for p in products if getattr(p, sync_field)}
        _logger.debug("Existing products found in Odoo matching refs %s: %s", product_refs, list(product_dict.keys()))

        # ── Bulk Fetch Existing Partners and Shipping Partners ──────────────────
        if partner_cache is None:
            partner_cache = {}
        if shipping_partner_cache is None:
            shipping_partner_cache = {}

        emails = {
            (o.get('data', {}).get('billing', {}).get('email') or '').strip().lower()
            for o in orders_data
            if o.get('data', {}).get('billing', {}).get('email')
        }
        emails.discard('')

        if emails:
            existing_partners = self.env['res.partner'].with_context(
                mail_create_nosubscribe=True, mail_create_nolog=True, tracking_disable=True
            ).search([
                ('email', 'in', list(emails)),
                ('type', 'in', ['contact', False]),
            ])
            for p in existing_partners:
                if p.email:
                    partner_cache[p.email.strip().lower()] = p

            parent_partner_ids = existing_partners.ids
            if parent_partner_ids:
                existing_delivery_partners = self.env['res.partner'].with_context(
                    mail_create_nosubscribe=True, mail_create_nolog=True, tracking_disable=True
                ).search([
                    ('parent_id', 'in', parent_partner_ids),
                    ('type', '=', 'delivery'),
                ])
                for dp in existing_delivery_partners:
                    cache_key = (
                        dp.parent_id.id,
                        (dp.street or '').strip(),
                        (dp.city or '').strip(),
                        (dp.zip or '').strip()
                    )
                    shipping_partner_cache[cache_key] = dp

        channable_totals = {}
        orders_vals_list = []
        orders_mapping = []

        for order_data in orders_data:
            channable_id = str(order_data.get('id', ''))
            # channel_id is the marketplace order reference (e.g. "123456789-8124879")
            market_ref = str(order_data.get('channel_id', '') or '')
            # status_shipped reflects the actual shipment state from Channable payload
            status = order_data.get('status_shipped', 'not_shipped')

            inner_data = order_data.get('data', {})
            billing_data = inner_data.get('billing', {})
            shipping_data = inner_data.get('shipping', {})
            products_data = inner_data.get('products', [])

            # ── Skip already-imported orders ─────────────────────────────────
            if channable_id in existing_channable_ids:
                _logger.debug("Skipping order %s because it already exists.", channable_id)
                continue

            # ── Partners ─────────────────────────────────────────────────────
            try:
                invoice_partner = self._get_or_create_partner(
                    billing_data,
                    marketplace,
                    country_cache=country_cache,
                    state_cache=state_cache,
                    partner_cache=partner_cache
                )
                shipping_partner = self._get_or_create_shipping_partner(
                    shipping_data,
                    invoice_partner,
                    marketplace,
                    country_cache=country_cache,
                    state_cache=state_cache,
                    shipping_partner_cache=shipping_partner_cache
                )
            except Exception as e:
                self._log_error(
                    f'Partner creation failed for order {channable_id}',
                    'create_order', e
                )
                continue

            # ── Fiscal position ───────────────────────────────────────────────
            fiscal_position_id = (
                marketplace.default_fiscal_position_id.id
                if marketplace.default_fiscal_position_id
                else False
            )
            is_business = (
                billing_data.get('company')
                or str(order_data.get('business_order', '')).lower() == 'true'
            )
            total_taxes = sum(item.get('tax', 0.0) for item in products_data)
            if (is_business and total_taxes == 0
                    and marketplace.intra_community_fiscal_position_id):
                fiscal_position_id = marketplace.intra_community_fiscal_position_id.id

            # ── Parse order date ──────────────────────────────────────────────
            raw_date = order_data.get('created', '')
            try:
                order_date = (
                    raw_date[:19].replace('T', ' ')
                    if raw_date
                    else fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
            except Exception:
                order_date = fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # ── Order lines ───────────────────────────────────────────────────
            order_lines = []
            order_failed = False

            for item in products_data:
                product_ref = str(
                    item.get('ean', '') if marketplace.sync_product_field == 'barcode'
                    else item.get('id', '')
                )
                title = item.get('title', 'Unknown Product')
                qty = float(item.get('quantity', 1))
                price = float(item.get('price', 0.0))

                product = product_dict.get(product_ref)
                if product:
                    _logger.debug("Product %s found in Odoo: %s", product_ref, product)
                if not product:
                    _logger.debug("Product %s not found. Attempting to auto-create...", product_ref)
                    # ── Auto-create product ───────────────────────────────────
                    try:
                        tmpl_vals = {
                            'name': title,
                            'list_price': price,
                            'type': 'consu',   # storable/consumable – adjust as needed
                            'sale_ok': True,
                            'purchase_ok': True,
                            'taxes_id': [(5, 0, 0)],
                            'supplier_taxes_id': [(5, 0, 0)],
                        }
                        if marketplace.sync_product_field == 'default_code':
                            tmpl_vals['default_code'] = product_ref
                        elif marketplace.sync_product_field == 'barcode':
                            tmpl_vals['barcode'] = product_ref

                        product_tmpl = self.env['product.template'].with_context(
                            mail_create_nosubscribe=True, mail_create_nolog=True, tracking_disable=True
                        ).create(tmpl_vals)
                        product = product_tmpl.product_variant_ids[:1] if product_tmpl.product_variant_ids else False
                        _logger.debug("Created product_tmpl: %s, product_variant: %s", product_tmpl, product)
                        if not product:
                            raise Exception("Product template was created but no variant is available.")

                        product_dict[product_ref] = product
                        # Informational – not an error; use _logger so it stays out of error records
                        _logger.info(
                            "Product auto-created: '%s' (ref: %s) for Channable order %s.",
                            title, product_ref, channable_id
                        )
                    except Exception as e:
                        err_trace = traceback.format_exc()
                        self._log_error(
                            f'Product creation failed: {product_ref}',
                            'sync_order',
                            f"Could not create product {product_ref} for order "
                            f"{channable_id}.\nError: {e}\nTraceback: {err_trace}"
                        )
                        order_failed = True
                        break

                # Determine UoM
                uom_id = product.uom_id.id if product else False
                line_vals = {
                    'product_id': product.id,
                    'name': title,
                    'product_uom_qty': qty,
                    'price_unit': price,
                    'tax_id': [(5, 0, 0)],
                }
                
                if uom_id:
                    line_vals['product_uom'] = uom_id
                _logger.debug("Appending line %s for order %s", line_vals, channable_id)
                order_lines.append((0, 0, line_vals))

            if order_failed:
                _logger.warning("Order %s skipped due to product creation failure.", channable_id)
                continue

            # ── Resolve Shipping Carrier ──────────────────────────────────────
            channable_ship_method = (
                inner_data.get('delivery_request', {}).get('method')
                or inner_data.get('delivery_request', {}).get('carrier')
                or inner_data.get('shipping', {}).get('method')
                or ''
            )
            _logger.info("[Channable] Mapped shipping method : %s", channable_ship_method)
            carrier = False
            if channable_ship_method:
                channable_ship_method_clean = str(channable_ship_method).strip().lower()
                matching_mapping = marketplace.shipping_mapping_ids.filtered(
                    lambda m: (m.channable_shipping_method or '').strip().lower() == channable_ship_method_clean
                )
                if matching_mapping:
                    carrier = matching_mapping[0].carrier_id
                    _logger.info("[Channable] Mapped shipping method '%s' to carrier: %s", channable_ship_method, carrier.name)
            
            if not carrier:
                carrier = marketplace.carrier_id
                if channable_ship_method:
                    _logger.info("[Channable] No mapping found for shipping method '%s', using default carrier: %s", channable_ship_method, carrier.name if carrier else 'None')

            # ── Shipping cost line ────────────────────────────────────────────
            # Shipping cost lives at data.price.shipping in the Channable payload
            shipping_cost = float(inner_data.get('price', {}).get('shipping', 0.0))
            if shipping_cost and carrier:
                carrier_product = carrier.product_id
                if carrier_product:
                    order_lines.append((0, 0, {
                        'product_id': carrier_product.id,
                        'name': carrier.name or _('Shipping'),
                        'product_uom_qty': 1,
                        'price_unit': shipping_cost,
                        'tax_id': [(5, 0, 0)],
                    }))

            # ── Order note / memo ─────────────────────────────────────────────
            # memo lives at data.extra.memo in the Channable payload
            memo = inner_data.get('extra', {}).get('memo', '')

            # ── Build sale.order vals ─────────────────────────────────────────
            order_vals = {
                # ── Core sale.order fields ─────────────────────────────────────
                'partner_id': invoice_partner.id,
                'partner_invoice_id': invoice_partner.id,
                'partner_shipping_id': shipping_partner.id,
                # Set client_order_ref so the marketplace reference appears
                # in the standard "Customer Reference" field
                'client_order_ref': market_ref,
                'date_order': order_date,
                'company_id': self.env.company.id,
                'warehouse_id': marketplace.warehouse_id.id,
                'fiscal_position_id': fiscal_position_id,
                'team_id': marketplace.team_id.id if marketplace.team_id else False,
                'pricelist_id': marketplace.pricelist_id.id if marketplace.pricelist_id else False,
                'note': memo,
                # ── Channable-specific fields ─────────────────────────────────
                'channable_marketplace_id': marketplace.id,
                'channable_order_id': channable_id,
                'channable_market_ref': market_ref,
                'channable_status': status,
                # ── Lines ─────────────────────────────────────────────────────
                'order_line': order_lines,
            }

            # Add carrier to deliver so the default delivery method is set
            if carrier:
                order_vals['carrier_id'] = carrier.id

            ch_total = float(order_data.get('price', 0.0))
            if not ch_total:
                ch_total = sum(float(item.get('price', 0.0)) * float(item.get('quantity', 1)) for item in products_data) + shipping_cost

            orders_vals_list.append(order_vals)
            orders_mapping.append((channable_id, ch_total))

        # ── Bulk Sales Order Creation with Fallback ──────────────────────────
        if orders_vals_list:
            try:
                _logger.info("Attempting optimistic batch creation of %d orders", len(orders_vals_list))
                created_orders = SaleOrder.with_context(
                    mail_create_nosubscribe=True, mail_create_nolog=True, tracking_disable=True
                ).create(orders_vals_list)
                new_orders |= created_orders
                
                # Map created orders back to their totals
                for order, (_, ch_total) in zip(created_orders, orders_mapping):
                    channable_totals[order.id] = ch_total
                    
            except Exception as batch_err:
                _logger.warning("Batch creation failed: %s. Falling back to single order creation.", str(batch_err))
                # Fallback to creating each order individually to isolate any errors
                for order_vals, (channable_id, ch_total) in zip(orders_vals_list, orders_mapping):
                    try:
                        order = SaleOrder.with_context(
                            mail_create_nosubscribe=True, mail_create_nolog=True, tracking_disable=True
                        ).create(order_vals)
                        new_orders |= order
                        channable_totals[order.id] = ch_total
                    except Exception as single_err:
                        err_trace = traceback.format_exc()
                        self._log_error(
                            f'Order insertion failed: {channable_id}',
                            'create_order',
                            f'Could not create order {channable_id}.\nError: {single_err}\nTraceback: {err_trace}'
                        )

        # ── Post-creation flow ────────────────────────────────────────────────
        self._post_create_flow(new_orders, marketplace, channable_totals)
        return {
            'synced': len(new_orders),
            'skipped': len(existing_channable_ids),
        }

    def _post_create_flow(self, new_orders, marketplace, channable_totals=None):
        """Confirm, invoice, and register payment based on marketplace settings.

        Operations are batched where possible and wrapped with mail/tracking
        bypass context to eliminate thousands of unnecessary chatter messages,
        follower subscriptions, and field-tracking writes during bulk import.
        Each batch falls back to per-order processing on failure so that a
        single bad order never blocks the rest.
        """
        if not new_orders:
            return

        channable_totals = channable_totals or {}

        # Context flags to suppress mail/tracking overhead on every ORM call
        _bypass_ctx = {
            'mail_create_nosubscribe': True,
            'mail_create_nolog': True,
            'mail_notrack': True,
            'tracking_disable': True,
        }

        # ── 0. Handle cancelled orders ────────────────────────────────────────
        cancelled_orders = new_orders.filtered(
            lambda o: o.channable_status in ('canceled', 'cancelled')
        )
        for order in cancelled_orders:
            try:
                order.with_context(disable_cancel_warning=True, **_bypass_ctx).action_cancel()
                order.message_post(
                    body=_("Order automatically cancelled in Odoo during import "
                           "due to Channable status: %s", order.channable_status)
                )
            except Exception as e:
                self._log_error('Order Auto-Cancellation Error', 'cancel_order', e, order.id)

        active_orders = new_orders - cancelled_orders
        if not active_orders:
            return

        # ── 1. Batch confirm quotations → sale orders ─────────────────────────
        confirmable_orders = self.env['sale.order']
        if marketplace.auto_validate_quotations or marketplace.auto_validate_orders:
            for order in active_orders:
                ch_total = channable_totals.get(order.id, 0.0)
                confirm_allowed = True
                if ch_total > 0.0 and marketplace.difference_threshold > 0.0:
                    diff = abs(order.amount_total - ch_total)
                    if diff > marketplace.difference_threshold:
                        self._log_error(
                            'Total Difference Threshold Exceeded',
                            'confirm_order',
                            f"Order {order.name} total ({order.amount_total}) differs from "
                            f"Channable total ({ch_total}) by {diff}, which exceeds the "
                            f"threshold of {marketplace.difference_threshold}. "
                            "The order has intentionally not been confirmed.",
                            order.id,
                        )
                        confirm_allowed = False
                if confirm_allowed:
                    confirmable_orders |= order

            if confirmable_orders:
                try:
                    confirmable_orders.with_context(**_bypass_ctx).action_confirm()
                except Exception:
                    _logger.warning(
                        "Batch confirmation failed, falling back to per-order.",
                        exc_info=True,
                    )
                    failed = self.env['sale.order']
                    for order in confirmable_orders:
                        try:
                            order.with_context(**_bypass_ctx).action_confirm()
                        except Exception as e:
                            self._log_error(
                                'Order Confirmation Error', 'confirm_order', e, order.id
                            )
                            failed |= order
                    confirmable_orders -= failed

        # Only orders that actually reached 'sale' state count as confirmed
        confirmed_orders = confirmable_orders.filtered(lambda o: o.state == 'sale')

        # ── 2. Validate stock pickings for shipped orders ─────────────────────
        # Per-order because we must set move quantities individually
        shipped_orders = confirmed_orders.filtered(
            lambda o: o.channable_status == 'shipped'
        )
        for order in shipped_orders:
            deliveries = order.picking_ids.filtered(
                lambda p: p.state not in ('done', 'cancel')
            )
            for delivery in deliveries:
                try:
                    delivery.with_context(**_bypass_ctx).action_assign()
                    for move in delivery.move_ids:
                        if move.state not in ('done', 'cancel'):
                            move.quantity = move.product_uom_qty
                    # Set sync status to done and bypass api trigger since
                    # it is already shipped on Channable
                    delivery.channable_sync_status = 'done'
                    delivery.with_context(
                        skip_channable_shipment_notify=True,
                        **_bypass_ctx,
                    ).button_validate()
                except Exception as e:
                    self._log_error(
                        'Delivery Auto-Validation Error', 'validate_picking', e, order.id
                    )

        # ── 3. Create & post invoices ───────────────────────────────────
        if confirmed_orders and marketplace.auto_validate_orders and marketplace.auto_validate_invoices:
            all_invoices = self.env['account.move']
            # Create draft invoices individually to prevent Odoo from grouping multiple orders
            # under the same customer into a single combined invoice.
            for order in confirmed_orders:
                try:
                    inv = order.with_context(**_bypass_ctx)._create_invoices()
                    all_invoices |= inv
                except Exception as e:
                    self._log_error(
                        'Order Invoice Creation Error', 'create_invoice', e, order.id
                    )

            # Post all created invoices in batch
            if all_invoices:
                try:
                    all_invoices.with_context(**_bypass_ctx).action_post()
                except Exception:
                    _logger.warning(
                        "Batch invoice posting failed, falling back to per-invoice.",
                        exc_info=True,
                    )
                    for invoice in all_invoices:
                        try:
                            invoice.with_context(**_bypass_ctx).action_post()
                        except Exception as e:
                            order_id = False
                            if hasattr(invoice, 'invoice_origin') and invoice.invoice_origin:
                                order = self.env['sale.order'].search(
                                    [('name', '=', invoice.invoice_origin)], limit=1
                                )
                                order_id = order.id if order else False
                            self._log_error(
                                'Invoice Posting Error', 'post_invoice', e, order_id
                            )

            # ── 4. Batch register payments ────────────────────────────────────
            if marketplace.payment_journal_id and all_invoices:
                self._register_invoice_payment(all_invoices, marketplace, _bypass_ctx)

    def _register_invoice_payment(self, invoices, marketplace, bypass_ctx=None):
        """
        Register payment on posted invoices using account.payment.register wizard,
        which is the standard Odoo way since v15.
        """
        bypass_ctx = bypass_ctx or {}
        payable = invoices.filtered(
            lambda inv: inv.state == 'posted' and inv.payment_state != 'paid'
        )
        if not payable:
            return

        today = fields.Date.today()
        journal_id = marketplace.payment_journal_id.id
        PayReg = self.env['account.payment.register']

        for invoice in payable:
            try:
                pay_ctx = {
                    'active_model': 'account.move',
                    'active_ids': invoice.ids,
                }
                pay_ctx.update(bypass_ctx)
                pay_wiz = PayReg.with_context(**pay_ctx).create({
                    'journal_id': journal_id,
                    'payment_date': today,
                    'amount': invoice.amount_residual,
                    'currency_id': invoice.currency_id.id,
                })
                pay_wiz.action_create_payments()
            except Exception as e:
                # Try to find the related sale order for error logging
                order_id = False
                if hasattr(invoice, 'invoice_origin') and invoice.invoice_origin:
                    order = self.env['sale.order'].search(
                        [('name', '=', invoice.invoice_origin)], limit=1
                    )
                    order_id = order.id if order else False
                self._log_error(
                    'Payment Registration Error', 'confirm_order', e, order_id
                )
