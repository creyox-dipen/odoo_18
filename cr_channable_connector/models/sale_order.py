# -*- coding: utf-8 -*-
# Part of Creyox Technologies
import base64
import datetime
import logging
import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    channable_status = fields.Char(
        string='Channable Status', copy=False,
        help='Current order status in Channable'
    )
    channable_market_ref = fields.Char(
        string='Market Reference (Channable)', copy=False
    )
    channable_order_id = fields.Char(string='Channable Order ID', copy=False)
    channable_marketplace_id = fields.Many2one(
        'channable.marketplace', string='Marketplace', copy=False
    )

    channable_error_ids = fields.One2many(
        'channable.sync.error', 'order_id', string='Sync Errors'
    )
    channable_error_count = fields.Integer(
        compute='_compute_channable_error_count', string='Error Count'
    )

    @api.depends('channable_error_ids')
    def _compute_channable_error_count(self):
        for order in self:
            order.channable_error_count = len(order.channable_error_ids)

    def action_view_channable_errors(self):
        self.ensure_one()
        return {
            'name': _('Channable Sync Errors'),
            'type': 'ir.actions.act_window',
            'res_model': 'channable.sync.error',
            'view_mode': 'list,form',
            'domain': [('order_id', '=', self.id)],
            'context': {'default_order_id': self.id},
        }

    def action_view_in_channable(self):
        self.ensure_one()
        if not self.channable_marketplace_id:
            raise UserError(_("This order is not associated with a Channable marketplace."))
        if not self.channable_order_id:
            raise UserError(_("No Channable Order ID found for this sale order."))

        project = self.channable_marketplace_id.project_id
        if not project:
            raise UserError(_("No Channable Project found for this marketplace."))

        connection = project.connection_id
        if not connection:
            raise UserError(_("No Channable Connection found for this project."))

        company_id = connection.company_id_num
        project_id = project.channable_identifier

        if not company_id or not project_id:
            raise UserError(_("Missing Company ID or Project ID in Channable configuration."))

        url = f"https://app.channable.com/companies/{company_id}/projects/{project_id}/orders/{self.channable_order_id}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _channable_get_connection_and_headers(self):
        """Return (connection, url_base, headers) for this order."""
        self.ensure_one()
        mp = self.channable_marketplace_id
        connection = mp.project_id.connection_id
        url_base = (
            f'https://api.channable.com/v1/companies/{connection.company_id_num}'
            f'/projects/{mp.project_id.channable_identifier}'
        )
        headers = {
            'Authorization': f'Bearer {connection.api_token.strip()}',
            'Content-Type': 'application/json',
        }
        return connection, url_base, headers

    def _channable_log_error(self, name, action, exc):
        self.env['channable.sync.error'].create({
            'name': name,
            'order_id': self.id,
            'marketplace_id': self.channable_marketplace_id.id,
            'action_attempted': action,
            'detailed_description': str(exc),
        })

    def _channable_create_credit_notes(self):
        """Automatically create and post credit notes for any posted invoices of this order."""
        for order in self:
            posted_invoices = order.invoice_ids.filtered(lambda inv: inv.move_type == 'out_invoice' and inv.state == 'posted')
            for invoice in posted_invoices:
                # Avoid duplicate credit notes
                already_refunded = order.invoice_ids.filtered(
                    lambda inv: inv.move_type == 'out_refund' and inv.state != 'cancel' and invoice.name in (inv.ref or '')
                )
                if not already_refunded:
                    try:
                        credit_notes = invoice._reverse_moves([{'ref': _('Automatically created due to Channable order cancellation.')}], cancel=True)
                        if credit_notes:
                            credit_notes.filtered(lambda m: m.state == 'draft').action_post()
                            for cn in credit_notes:
                                order.message_post(body=_("Credit Note automatically created and posted for invoice %s: %s", invoice.name, cn.name))
                    except Exception as inv_err:
                        _logger.warning("Could not automatically create credit note for invoice %s of order %s: %s", invoice.name, order.name, str(inv_err))

    # ── Cron ─────────────────────────────────────────────────────────────────

    @api.model
    def cron_channable_notify_shipped(self):
        """Cron: notify Channable for all completed-but-unsynced deliveries."""
        orders = self.search([
            ('state', 'in', ['sale', 'done']),
            ('channable_marketplace_id', '!=', False),
            ('channable_status', 'not in', ['shipped', 'canceled', 'cancelled', 'manual']),
            ('picking_ids.state', '=', 'done'),
            ('picking_ids.channable_sync_status', '=', 'pending'),
            ('picking_ids.date_done', '>=',
             fields.Datetime.now() - datetime.timedelta(days=5)),
        ])
        for order in orders:
            try:
                order.action_channable_notify_shipped()
            except Exception:
                pass

    # ── Public Actions ────────────────────────────────────────────────────────

    def action_channable_sync_state(self):
        """Pull current status from Channable and update the record."""
        for order in self.filtered(lambda o: o.channable_marketplace_id and o.channable_order_id):
            try:
                connection, url_base, headers = order._channable_get_connection_and_headers()
                url = f'{url_base}/orders/{order.channable_order_id}'
                resp = requests.get(url, headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                _logger.warning(
                    "[Channable Status Sync] Raw Response for order %s | URL: %s\nPayload: %s",
                    order.name, resp.url, data
                )
                if 'order' in data and 'status_shipped' in data['order']:
                    old_status = order.channable_status
                    new_status = data['order']['status_shipped']
                    if old_status != new_status:
                        order.channable_status = new_status
                        order.message_post(body=_("Channable Status updated: %s &rarr; %s", old_status, new_status))
                        if new_status in ['canceled', 'cancelled'] and order.state != 'cancel':
                            try:
                                order.action_cancel()
                                order.message_post(body=_("Order automatically cancelled in Odoo due to Channable cancellation."))
                                order._channable_create_credit_notes()
                            except Exception as cancel_err:
                                order.message_post(body=_("Failed to automatically cancel the order in Odoo: %s", str(cancel_err)))
            except Exception as e:
                order._channable_log_error('Status Sync Error', 'sync_state', e)

    def action_channable_sync_order(self):
        """Re-fetch the order from Channable and update editable fields."""
        for order in self.filtered(lambda o: o.channable_marketplace_id and o.channable_order_id):
            try:
                connection, url_base, headers = order._channable_get_connection_and_headers()
                url = f'{url_base}/orders/{order.channable_order_id}'
                resp = requests.get(url, headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                _logger.warning(
                    "[Channable Full Order Sync] Raw Response for order %s | URL: %s\nPayload: %s",
                    order.name, resp.url, data
                )
                order_data = data.get('order', {})
                if order_data:
                    old_status = order.channable_status
                    new_status = order_data.get('status_shipped', order.channable_status)
                    if old_status != new_status:
                        order.channable_status = new_status
                        order.message_post(body=_("Channable Status updated: %s &rarr; %s", old_status, new_status))
                        if new_status in ['canceled', 'cancelled'] and order.state != 'cancel':
                            try:
                                order.action_cancel()
                                order.message_post(body=_("Order automatically cancelled in Odoo due to Channable cancellation."))
                                order._channable_create_credit_notes()
                            except Exception as cancel_err:
                                order.message_post(body=_("Failed to automatically cancel the order in Odoo: %s", str(cancel_err)))
                    # Update client reference if it changed
                    if order_data.get('channel_order_id'):
                        order.channable_market_ref = str(order_data['channel_order_id'])
                    # Sync the customer note / memo from Channable if present
                    if order_data.get('memo'):
                        order.note = order_data['memo']
            except Exception as e:
                order._channable_log_error('Sync Order Error', 'sync_order', e)

    def action_channable_sync_attachments(self):
        """Download / link attachments from Channable order details."""
        for order in self.filtered(lambda o: o.channable_marketplace_id and o.channable_order_id):
            try:
                connection, url_base, headers = order._channable_get_connection_and_headers()
                url = f'{url_base}/orders/{order.channable_order_id}'
                resp = requests.get(url, headers=headers, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                order_data = data.get('order', {})
                attachments = order_data.get('attachments', [])
                saving_type = order.channable_marketplace_id.saving_attachments

                for att in attachments:
                    att_url = att.get('url', '')
                    att_name = att.get('name', 'channable_attachment')
                    if not att_url:
                        continue
                    if saving_type == 'download':
                        file_resp = requests.get(att_url, timeout=30)
                        file_resp.raise_for_status()
                        self.env['ir.attachment'].create({
                            'name': att_name,
                            'datas': base64.b64encode(file_resp.content),
                            'res_model': 'sale.order',
                            'res_id': order.id,
                        })
                    else:
                        # Save URL as a chatter message link
                        order.message_post(
                            body=_(
                                'Channable attachment: <a href="%s" target="_blank">%s</a>',
                                att_url, att_name
                            )
                        )
            except Exception:
                pass

    def action_channable_notify_shipped(self):
        """POST shipment tracking info to Channable."""
        for order in self.filtered(lambda o: o.channable_marketplace_id and o.channable_order_id):
            # Look for completed deliveries that haven't been synced yet
            deliveries = order.picking_ids.filtered(
                lambda p: p.state == 'done'
                and p.picking_type_code == 'outgoing'
                and p.channable_sync_status == 'pending'
            )
            if not deliveries:
                deliveries = order.picking_ids.filtered(
                    lambda p: p.state == 'done' and p.picking_type_code == 'outgoing'
                )
            if not deliveries:
                raise UserError(_('No completed deliveries found for order %s.', order.name))

            delivery = deliveries[0]
            tracking_ref = getattr(delivery, 'carrier_tracking_ref', False) or getattr(delivery, 'tracking_reference', '') or ''
            carrier = getattr(delivery, 'carrier_id', False) or order.channable_marketplace_id.carrier_id
            transporter_code = (
                carrier.channable_transporter_code if carrier and carrier.channable_transporter_code else 'Other'
            )

            try:
                connection, url_base, headers = order._channable_get_connection_and_headers()
                url = f'{url_base}/orders/{order.channable_order_id}/shipment'
                payload = {
                    'tracking_code': tracking_ref or '',
                    'transporter': transporter_code,
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=15)
                resp.raise_for_status()
                order.channable_status = 'shipped'
                delivery.channable_sync_status = 'done'
                order.message_post(body=_("Shipment tracking %s successfully sent to Channable via %s.", tracking_ref or 'N/A', transporter_code))
            except requests.exceptions.HTTPError as e:
                err_msg = str(e)
                if e.response is not None:
                    err_msg += f"\nResponse body: {e.response.text}"
                order._channable_log_error(
                    'Shipment Notification Error', 'update_shipment', err_msg
                )
                delivery.channable_sync_status = 'error'

    def action_channable_cancel_order(self):
        """POST cancellation to Channable (only when order is already cancelled in Odoo)."""
        for order in self.filtered(
            lambda o: o.channable_marketplace_id and o.channable_order_id and o.state == 'cancel'
        ):
            try:
                connection, url_base, headers = order._channable_get_connection_and_headers()
                url = f'{url_base}/orders/{order.channable_order_id}/cancel'
                resp = requests.post(url, headers=headers, json={}, timeout=15)
                resp.raise_for_status()
                order.channable_status = 'canceled'
                order.message_post(body=_("Order successfully cancelled in Channable."))
            except Exception as e:
                order._channable_log_error('Cancel Notification Error', 'cancel_order', e)
