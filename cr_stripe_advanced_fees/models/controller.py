# controllers/main.py
from odoo import http
from odoo.http import request

class PublicStripeInfo(http.Controller):
    @http.route(['/custom/stripe/provider_config'], type='json', auth='public', csrf=False)
    def get_stripe_provider_config(self):
        provider = request.env['payment.provider'].sudo().search([('code', '=', 'stripe')], limit=1)
        if not provider:
            return {}
        line_ids_data = []
        for line in provider.line_ids:
            pm = line.payment_method_id
            line_ids_data.append({
                'payment_method_code': pm.code,
                'payment_method_name': pm.name,
                'default_method': line.default_method,
                'fix_domestic_fees': line.fix_domestic_fees,
                'var_domestic_fees': line.var_domestic_fees,
                'is_free_domestic': line.is_free_domestic,
                'free_domestic_amount': line.free_domestic_amount,
                'fix_international_fees': line.fix_international_fees,
                'var_international_fees': line.var_international_fees,
                'is_free_international': line.is_free_international,
                'free_international_amount': line.free_international_amount,
            })
        return {
            'is_extra_fees': provider.is_extra_fees,
            'line_ids': line_ids_data,
            'company_id': provider.company_id.id,
        }

    @http.route(['/custom/stripe/company_country/<int:company_id>'], type='json', auth='public', csrf=False)
    def get_company_country(self, company_id):
        company = request.env['res.company'].sudo().browse(company_id)
        return {'country_id': company.country_id.id if company.country_id else None}

    @http.route(['/custom/stripe/order_partner_country/<int:order_id>'], type='json', auth='public', csrf=False)
    def get_order_partner_country(self, order_id):
        order = request.env['sale.order'].sudo().browse(order_id)
        partner = order.partner_shipping_id  # Use billing partner to match backend transaction logic
        return {'country_id': partner.country_id.id if partner and partner.country_id else None}

    # @http.route(['/custom/stripe/token_method/<int:token_id>'], type='json', auth='public', csrf=False)
    # def get_token_payment_method(self, token_id):
    #     token = request.env['payment.token'].sudo().browse(token_id)
    #     if not token or token.provider_code != 'stripe':
    #         return {'payment_method_code': 'card'}
    #     provider = token.provider_id
    #     if not provider:
    #         return {'payment_method_code': 'card'}
    #     try:
    #         # Retrieve the payment method from Stripe to get the card brand
    #         stripe_pm = provider._stripe_make_request('GET', f'/v1/payment_methods/{token.acquirer_ref}')
    #         if stripe_pm and 'card' in stripe_pm:
    #             brand = stripe_pm['card'].get('brand')
    #             if brand and brand != 'unknown':
    #                 return {'payment_method_code': brand.lower()}
    #     except Exception as e:
    #         print(f"Could not retrieve token brand for token {token_id} : {e} ")
    #     return {'payment_method_code': 'card'}

    @http.route(['/custom/stripe/token_method/<int:token_id>'], type='json', auth='public', csrf=False)
    def get_token_payment_method(self, token_id):
        # Just redirect to the new unified one
        return self.get_payment_method_code(token_id=token_id)

    @http.route(['/custom/stripe/payment_method_code'], type='json', auth='public', csrf=False)
    def get_payment_method_code(self, **kwargs):
        """
        Unified endpoint:
        - If token_id is passed → returns actual card brand (visa, mastercard, amex, etc.)
        - If no token_id → returns 'card' (used for new payments before brand detection)
        """
        token_id = kwargs.get('token_id')

        if token_id:
            token = request.env['payment.token'].sudo().browse(int(token_id))
            print("Token : ",token)
            print("token provider : ",token.provider_code)
            if not token.exists() or token.provider_code != 'stripe':
                return {'payment_method_code': 'card'}

            # This is the correct field in Odoo 16+
            stripe_pm_id = token.stripe_payment_method
            print(stripe_pm_id)
            if not stripe_pm_id:
                return {'payment_method_code': 'card'}

            provider = token.provider_id
            try:
                stripe_pm = provider._stripe_make_request(
                    f'/v1/payment_methods/{stripe_pm_id}',
                    method='GET'
                )
                print("stripe PM : ",stripe_pm)
                if stripe_pm.get('card', {}).get('brand'):
                    brand = stripe_pm['card']['brand'].lower()
                    # Optional: map known brands if you use them as codes in payment.method
                    brand_map = {
                        'visa': 'visa',
                        'mastercard': 'mastercard',
                        'american express': 'amex',
                        'discover': 'discover',
                        'diners club': 'diners',
                        'jcb': 'jcb',
                        'unionpay': 'unionpay',
                    }
                    print("Brand : ",brand_map.get(brand, 'card'))
                    return {'payment_method_code': brand_map.get(brand, 'card')}
            except Exception as e:
                    print(f"Could not retrieve token brand for token {token_id}: {e}")

            return {'payment_method_code': 'card'}

        # No token → new card entry
        return {'payment_method_code': 'card'}