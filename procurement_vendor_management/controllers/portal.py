# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError

class VendorBridgePortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        
        # Count RFQs assigned or invited
        RFQ = request.env['purchase.order']
        domain_rfqs = [
            ('hackathon_state', 'in', ['pending_vendor_bid', 'under_review', 'pending_approval']),
            '|', ('partner_id', '=', partner.id), ('invited_vendor_ids', 'in', partner.id)
        ]
        if 'rfq_count' in counters:
            values['rfq_count'] = RFQ.search_count(domain_rfqs) if RFQ.has_access('read') else 0

        # Count Purchase Orders confirmed
        domain_pos = [
            ('hackathon_state', '=', 'po_created'),
            ('partner_id', '=', partner.id)
        ]
        if 'purchase_count' in counters:
            values['purchase_count'] = RFQ.search_count(domain_pos) if RFQ.has_access('read') else 0

        # Count Vendor Quotations submitted
        Quotation = request.env['vendor.quotation']
        domain_quotes = [('vendor_id', '=', partner.id)]
        if 'quotation_count' in counters:
            values['quotation_count'] = Quotation.search_count(domain_quotes) if Quotation.has_access('read') else 0

        return values

    # --- Portal Routes ---

    @http.route(['/my/hackathon/rfqs', '/my/hackathon/rfqs/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_rfqs(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id

        # Use sudo() to bypass ORM record rules which can be unreliable with Many2many domains
        # Then filter explicitly to only RFQs this partner is the vendor of OR is invited to
        domain = [
            ('hackathon_state', 'in', ['pending_vendor_bid', 'under_review', 'pending_approval', 'approved', 'rejected', 'po_created']),
            '|', ('partner_id', '=', partner.id), ('invited_vendor_ids', 'in', [partner.id])
        ]

        RFQ = request.env['purchase.order'].sudo()

        # Count for pager
        count = RFQ.search_count(domain)

        # Make pager
        pager = portal_pager(
            url="/my/hackathon/rfqs",
            total=count,
            page=page,
            step=10
        )

        rfqs = RFQ.search(domain, order="create_date desc", limit=10, offset=pager['offset'])

        values.update({
            'rfqs': rfqs,
            'page_name': 'rfq',
            'pager': pager,
            'default_url': '/my/hackathon/rfqs',
        })
        return request.render("procurement_vendor_management.portal_my_rfqs", values)

    @http.route(['/my/hackathon/rfqs/<int:order_id>'], type='http', auth="user", website=True)
    def portal_rfq_detail(self, order_id=None, **kw):
        partner = request.env.user.partner_id
        try:
            # Use sudo() to load the record, then manually verify access
            order = request.env['purchase.order'].sudo().browse(order_id)
            # Check access: must be primary vendor OR in invited vendors list
            if not order.exists() or (order.partner_id.id != partner.id and partner.id not in order.invited_vendor_ids.ids):
                raise AccessError(_("You do not have access to this RFQ."))
        except (AccessError, MissingError):
            return request.redirect('/my/hackathon/rfqs')

        # Check if this vendor already submitted a quotation for this RFQ
        existing_quotation = request.env['vendor.quotation'].search([
            ('purchase_id', '=', order.id),
            ('vendor_id', '=', partner.id)
        ], limit=1)

        # Get attachments associated with the PO
        attachments = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'purchase.order'),
            ('res_id', '=', order.id)
        ])

        values = {
            'order': order,
            'existing_quotation': existing_quotation,
            'attachments': attachments,
            'page_name': 'rfq',
        }
        return request.render("procurement_vendor_management.portal_rfq_detail", values)

    @http.route(['/my/hackathon/rfqs/<int:order_id>/submit_quotation'], type='http', auth="user", methods=['POST'], website=True)
    def portal_submit_quotation(self, order_id=None, **post):
        partner = request.env.user.partner_id
        try:
            # Use sudo() to load the record, then manually verify access
            order = request.env['purchase.order'].sudo().browse(order_id)
            if not order.exists() or (order.partner_id.id != partner.id and partner.id not in order.invited_vendor_ids.ids):
                raise AccessError(_("You do not have access to this RFQ."))
        except (AccessError, MissingError):
            return request.redirect('/my/hackathon/rfqs')

        if order.hackathon_state not in ('draft', 'pending_vendor_bid', 'under_review'):
            return request.redirect(f'/my/hackathon/rfqs/{order.id}?error=state')

        # Prevent double submission
        existing = request.env['vendor.quotation'].search([
            ('purchase_id', '=', order.id),
            ('vendor_id', '=', partner.id)
        ], limit=1)
        if existing:
            return request.redirect(f'/my/hackathon/rfqs/{order.id}?error=duplicate')

        # Read delivery lead days and comments
        try:
            delivery_days = int(post.get('delivery_days', 7))
        except ValueError:
            delivery_days = 7

        notes = post.get('notes', '')

        # Build quotation lines
        quotation_lines = []
        for line in order.order_line:
            param_name = f'price_unit_line_{line.id}'
            try:
                price_unit = float(post.get(param_name, 0.0))
            except ValueError:
                price_unit = 0.0
            
            quotation_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'quantity': line.product_qty,
                'price_unit': price_unit,
            }))

        # Create Vendor Quotation
        quotation = request.env['vendor.quotation'].create({
            'purchase_id': order.id,
            'vendor_id': partner.id,
            'delivery_days': delivery_days,
            'notes': notes,
            'state': 'draft',
            'line_ids': quotation_lines,
        })

        # Submit it
        quotation.action_submit()

        return request.redirect(f'/my/hackathon/rfqs/{order.id}?success=1')

    @http.route(['/my/hackathon/quotations', '/my/hackathon/quotations/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_quotations(self, page=1, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        Quotation = request.env['vendor.quotation']

        domain = [('vendor_id', '=', partner.id)]
        count = Quotation.search_count(domain)

        pager = portal_pager(
            url="/my/hackathon/quotations",
            total=count,
            page=page,
            step=10
        )

        quotations = Quotation.search(domain, order="submission_date desc", limit=10, offset=pager['offset'])

        values.update({
            'quotations': quotations,
            'page_name': 'quotation',
            'pager': pager,
            'default_url': '/my/hackathon/quotations',
        })
        return request.render("procurement_vendor_management.portal_my_quotations", values)

    @http.route(['/my/hackathon/purchase_orders', '/my/hackathon/purchase_orders/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_purchase_orders(self, page=1, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        RFQ = request.env['purchase.order']

        domain = [
            ('hackathon_state', '=', 'po_created'),
            ('partner_id', '=', partner.id)
        ]
        count = RFQ.search_count(domain)

        pager = portal_pager(
            url="/my/hackathon/purchase_orders",
            total=count,
            page=page,
            step=10
        )

        orders = RFQ.search(domain, order="date_order desc", limit=10, offset=pager['offset'])

        values.update({
            'orders': orders,
            'page_name': 'purchase_order',
            'pager': pager,
            'default_url': '/my/hackathon/purchase_orders',
        })
        return request.render("procurement_vendor_management.portal_my_purchase_orders", values)
