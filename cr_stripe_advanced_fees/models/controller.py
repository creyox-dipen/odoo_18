# controllers/main.py

from odoo import http
from odoo.http import request

class PublicStripeInfo(http.Controller):

    @http.route(['/custom/stripe/provider_config'], type='json', auth='public', csrf=False)
    def get_stripe_provider_config(self):
        provider = request.env['payment.provider'].sudo().search([('code', '=', 'stripe')], limit=1)
        if not provider:
            return {}
        return {
            'is_extra_fees': provider.is_extra_fees,
            'is_free_domestic': provider.is_free_domestic,
            'is_free_international': provider.is_free_international,
            'free_domestic_amount': provider.free_domestic_amount,
            'free_international_amount': provider.free_international_amount,
            'fix_domestic_fees': provider.fix_domestic_fees,
            'var_domestic_fees': provider.var_domestic_fees,
            'fix_international_fees': provider.fix_international_fees,
            'var_international_fees': provider.var_international_fees,
            'company_id': provider.company_id.id,
        }

    @http.route(['/custom/stripe/company_country/<int:company_id>'], type='json', auth='public', csrf=False)
    def get_company_country(self, company_id):
        company = request.env['res.company'].sudo().browse(company_id)
        return {'country_id': company.country_id.id if company.country_id else None}

    @http.route(['/custom/stripe/order_shipping_country/<int:order_id>'], type='json', auth='public', csrf=False)
    def get_order_shipping_country(self, order_id):
        order = request.env['sale.order'].sudo().browse(order_id)
        partner = order.partner_shipping_id
        return {'country_id': partner.country_id.id if partner and partner.country_id else None}
