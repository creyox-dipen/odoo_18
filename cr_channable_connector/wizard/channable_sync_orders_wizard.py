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
            if marketplace.valid_states:
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

    def _get_or_create_partner(self, billing_data, marketplace):
        """
        Find an existing res.partner by e-mail or create a new one.
        Returns a res.partner record (invoice / billing address).
        """
        Partner = self.env['res.partner']
        email = (billing_data.get('email') or '').strip().lower()

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
                country = self.env['res.country'].search(
                    [('code', '=ilike', country_code[:2])], limit=1
                )
            state_code = billing_data.get('state_code') or billing_data.get('state', '')
            if country and state_code:
                state = self.env['res.country.state'].search([
                    ('country_id', '=', country.id),
                    ('code', '=ilike', state_code),
                ], limit=1)

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

            partner = Partner.create(partner_vals)

        return partner

    def _get_or_create_shipping_partner(self, shipping_data, invoice_partner, marketplace):
        """
        Return a shipping address partner.
        - If the shipping address matches the billing address, reuse invoice_partner.
        - Otherwise create (or find) a child 'delivery' address linked to invoice_partner.
        """
        Partner = self.env['res.partner']

        ship_street = (shipping_data.get('street') or '').strip()
        ship_city = (shipping_data.get('city') or '').strip()
        ship_zip = (shipping_data.get('zip_code') or '').strip()

        # Quick equality check
        if (ship_street == (invoice_partner.street or '').strip()
                and ship_city == (invoice_partner.city or '').strip()
                and ship_zip == (invoice_partner.zip or '').strip()):
            return invoice_partner

        # Resolve country/state for shipping
        country = False
        state = False
        country_code = shipping_data.get('country_code') or shipping_data.get('country', '')
        if country_code:
            country = self.env['res.country'].search(
                [('code', '=ilike', country_code[:2])], limit=1
            )
        state_code = shipping_data.get('state_code') or shipping_data.get('state', '')
        if country and state_code:
            state = self.env['res.country.state'].search([
                ('country_id', '=', country.id),
                ('code', '=ilike', state_code),
            ], limit=1)

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
            shipping_partner = Partner.create(ship_vals)

        return shipping_partner

    # ── Main action ───────────────────────────────────────────────────────────

    def action_import_orders(self):
        self.ensure_one()
        _logger.warning("[Channable] action_import_orders CALLED - import_by_id=%s, order_ids_str=%s", self.import_by_id, self.order_ids_str)
        marketplace = self.marketplace_id
        connection = marketplace.project_id.connection_id

        headers = {
            'Authorization': f'Bearer {connection.api_token.strip()}',
            'Content-Type': 'application/json',
        }
        # Use v2 endpoint – the v1 endpoint is deprecated and returns 404
        # when status + date range parameters are combined.
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

        # Build the list of statuses to filter on.
        # If any of the status boolean fields are checked, use them.
        # Otherwise fall back to the marketplace's valid_states (comma-separated).
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
            
            # If no check-box is checked, fallback to valid_states on marketplace
            if not statuses and marketplace.valid_states:
                raw_states = [s.strip() for s in marketplace.valid_states.split(',') if s.strip()]
                # Normalise 'canceled' (single-l Odoo spelling) → 'cancelled' (API spelling)
                statuses = ['cancelled' if s == 'canceled' else s for s in raw_states]

        orders_data = []
        try:
            if self.import_by_id and self.order_ids_str:
                # Channable's list endpoint doesn't support filtering by order_ids query parameter.
                # We must fetch each order individually via /orders/{order_id} and compile them.
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
                # v2 supports status as a repeated query param or array.
                # We issue one request per status and deduplicate by Channable order id.
                seen_order_ids = set()
                for status in statuses:
                    req_params = params.copy()
                    req_params['status'] = status
                    response = requests.get(url, headers=headers, params=req_params, timeout=30)
                    response.raise_for_status()
                    data = response.json()
                    _logger.warning(
                        "[Channable] Raw API response | status=%s | URL: %s\n%s",
                        status, response.url, data
                    )
                    for o in data.get('orders', []):
                        o_id = o.get('id')
                        if o_id and o_id not in seen_order_ids:
                            seen_order_ids.add(o_id)
                            orders_data.append(o)
            else:
                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                _logger.warning(
                    "[Channable] Raw API response | URL: %s\n%s",
                    response.url, data
                )
                orders_data = data.get('orders', [])
        except Exception as e:
            self._log_error('API Fetch Error', 'sync_order', e)
            return {'type': 'ir.actions.act_window_close'}

        if not orders_data:
            return {'type': 'ir.actions.act_window_close'}


        SaleOrder = self.env['sale.order']
        new_orders = self.env['sale.order']

        # ── Bulk Fetch Existing Orders ─────────────────────────────────────────
        _logger.warning("[Channable] Total orders fetched from API: %d", len(orders_data))
        if orders_data:
            _logger.warning("[Channable] First order raw payload:\n%s", orders_data[0])

        channable_ids = [str(o.get('id', '')) for o in orders_data if o.get('id')]
        _logger.debug("Found %d orders from Channable API", len(channable_ids))
        existing_orders = SaleOrder.search([('channable_order_id', 'in', channable_ids)])
        existing_channable_ids = set(existing_orders.mapped('channable_order_id'))
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

        existing_products = self.env['product.product'].search([
            (marketplace.sync_product_field, 'in', product_refs)
        ])
        _logger.debug("Existing products found in Odoo matching refs %s: %s", product_refs, existing_products.mapped(marketplace.sync_product_field))
        product_dict = {
            getattr(p, marketplace.sync_product_field): p
            for p in existing_products if getattr(p, marketplace.sync_product_field)
        }

        channable_totals = {}

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
                invoice_partner = self._get_or_create_partner(billing_data, marketplace)
                shipping_partner = self._get_or_create_shipping_partner(
                    shipping_data, invoice_partner, marketplace
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

                        product_tmpl = self.env['product.template'].create(tmpl_vals)
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
                    'tax_ids': [(5, 0, 0)],
                }
                
                if uom_id:
                    line_vals['product_uom_id'] = uom_id
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
                        'tax_ids': [(5, 0, 0)], 
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

            try:
                _logger.debug("Attempting to create sale.order with vals: %s", order_vals)
                new_order = SaleOrder.create(order_vals)
                _logger.info("Created sale.order %s for Channable order %s", new_order.name, channable_id)
                new_orders |= new_order
                
                ch_total = float(order_data.get('price', 0.0))
                if not ch_total:
                    ch_total = sum(float(item.get('price', 0.0)) * float(item.get('quantity', 1)) for item in products_data) + shipping_cost
                channable_totals[new_order.id] = ch_total
                
            except Exception as e:
                err_trace = traceback.format_exc()
                self._log_error(
                    f'Order insertion failed: {channable_id}',
                    'create_order',
                    f'Could not create order {channable_id}.\nError: {e}\nTraceback: {err_trace}'
                )
                continue

        # ── Post-creation flow ────────────────────────────────────────────────
        self._post_create_flow(new_orders, marketplace, channable_totals)

        return {'type': 'ir.actions.act_window_close'}

    def _post_create_flow(self, new_orders, marketplace, channable_totals=None):
        """Confirm, invoice, and register payment based on marketplace settings."""
        if not new_orders:
            return

        channable_totals = channable_totals or {}

        for order in new_orders:
            order.message_post(body=_("Order successfully imported from Channable. Market ID: %s", order.channable_order_id))

            # If order status is canceled or cancelled, cancel it immediately in Odoo and skip confirmation/invoicing/pickings
            if order.channable_status in ['canceled', 'cancelled']:
                try:
                    order.action_cancel()
                    order.message_post(body=_("Order automatically cancelled in Odoo during import due to Channable status: %s", order.channable_status))
                except Exception as e:
                    self._log_error('Order Auto-Cancellation Error', 'cancel_order', e, order.id)
                continue

            # 1. Confirm quotation → sale order
            confirmed = False
            if marketplace.auto_validate_quotations or marketplace.auto_validate_orders:
                # Check difference threshold
                ch_total = channable_totals.get(order.id, 0.0)
                confirm_allowed = True
                if ch_total > 0.0 and marketplace.difference_threshold > 0.0:
                    diff = abs(order.amount_total - ch_total)
                    if diff > marketplace.difference_threshold:
                        self._log_error(
                            'Total Difference Threshold Exceeded', 
                            'confirm_order', 
                            f"Order {order.name} total ({order.amount_total}) differs from Channable total ({ch_total}) "
                            f"by {diff}, which exceeds the threshold of {marketplace.difference_threshold}. "
                            "The order has intentionally not been confirmed.",
                            order.id
                        )
                        confirm_allowed = False
                
                if confirm_allowed:
                    try:
                        order.action_confirm()
                        confirmed = True
                    except Exception as e:
                        self._log_error('Order Confirmation Error', 'confirm_order', e, order.id)
            # 2. Validate stock picking automatically if the order is already marked as shipped in Channable
            if confirmed and order.channable_status == 'shipped':
                deliveries = order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'])
                for delivery in deliveries:
                    try:
                        delivery.action_assign()
                        for move in delivery.move_ids:
                            if move.state not in ['done', 'cancel']:
                                move.quantity = move.product_uom_qty
                        # Set sync status to done and bypass api trigger since it is already shipped on Channable
                        delivery.channable_sync_status = 'done'
                        delivery.with_context(skip_channable_shipment_notify=True).button_validate()
                    except Exception as e:
                        self._log_error('Delivery Auto-Validation Error', 'validate_picking', e, order.id)

            # 3. Create & post invoice
            if confirmed and marketplace.auto_validate_orders and marketplace.auto_validate_invoices:
                try:
                    invoices = order._create_invoices()
                    invoices.action_post()

                    # 4. Register payment via the configured journal
                    if marketplace.payment_journal_id and invoices:
                        self._register_invoice_payment(invoices, order, marketplace)

                except Exception as e:
                    self._log_error(
                        'Order Invoice / Payment Error', 'confirm_order', e, order.id
                    )

    def _register_invoice_payment(self, invoices, order, marketplace):
        """
        Register payment on posted invoices using account.payment.register wizard,
        which is the standard Odoo way since v15.
        """
        for invoice in invoices.filtered(lambda inv: inv.state == 'posted'
                                         and inv.payment_state != 'paid'):
            try:
                # Use the built-in payment register wizard
                ctx = {
                    'active_model': 'account.move',
                    'active_ids': invoice.ids,
                }
                pay_wiz = self.env['account.payment.register'].with_context(**ctx).create({
                    'journal_id': marketplace.payment_journal_id.id,
                    'payment_date': fields.Date.today(),
                    'amount': invoice.amount_residual,
                    'currency_id': invoice.currency_id.id,
                })
                pay_wiz.action_create_payments()
            except Exception as e:
                self._log_error(
                    'Payment Registration Error', 'confirm_order', e, order.id
                )
