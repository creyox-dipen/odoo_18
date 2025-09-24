# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import http
from odoo.http import request

class StripeCancelController(http.Controller):
    @http.route(['/my/stripe/cancel'], type='http', auth='public', website=True)
    def stripe_cancel(self, tx_id=None, **kwargs):
        # Mark transaction canceled
        if tx_id:
            tx = request.env['payment.transaction'].sudo().browse(int(tx_id))
            if tx and tx.state not in ['done', 'cancel']:
                tx.sudo()._set_canceled()

        # Redirect to the portal invoice page
        invoice_id = tx.invoice_ids.id if tx and tx.invoice_ids else None
        if invoice_id:
            return request.redirect('/my/invoices/%s?access_token=%s' % (
                invoice_id, tx.invoice_ids.access_token))
        else:
            # fallback: redirect to invoices list
            return request.redirect('/my/invoices')

