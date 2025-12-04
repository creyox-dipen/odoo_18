# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class PaymentFeesController(WebsiteSale):

    @http.route("/payment/form", type="http", auth="public", website=True)
    # These controller is used to get the payment form details from the website page
    def payment_form(self, **kwargs):
        return request.render(
            "cr_website_payment_fee.payment_form",
            {
                "collapse_payment_methods": False,
            },
        )

    @http.route(["/shop/payment/transaction"], type="json", auth="public", website=True)
    # These controller is used to get the payment transaction against the sale order from the website page
    def payment_transaction(self, **post):
        provider_code = post.get("provider_code")
        order = request.website.sale_get_order()
        if order and provider_code:
            order.write({"provider_code": provider_code})

        return request.redirect("/shop/confirmation")

    @http.route("/shop/get_order_data", type="json", auth="public", website=True)
    # These controller is used to get the data of sale order created in backend
    def get_order_data(self, **kwargs):
        order = request.website.sale_get_order()
        if not order:
            return {"error": "No sale order found"}
        return {
            "order": {
                "id": order.id,
                "amount_total": order.amount_total,
                "cart_quantity": order.cart_quantity,
                "currency_id": {
                    "name": order.currency_id.name,
                    "symbol": order.currency_id.symbol,
                },
                "website_order_line": [
                    {
                        "product_id": line.product_id.id,
                        "name_short": line.name_short,
                        "product_uom_qty": line.product_uom_qty,
                        "price_subtotal": line.price_subtotal,
                        "price_total": line.price_total,
                    }
                    for line in order.website_order_line
                ],
            }
        }

    @http.route("/shop/update_order_provider", type="json", auth="public", website=True)
    # These controller get the sale order data, provider details, and update the provider when selected from the website page /shop/payment
    def update_order_provider(self, order_id, provider_code, **kwargs):
        try:
            order = request.env["sale.order"].sudo().browse(int(order_id)).exists()
            if not order:
                return {"success": False, "error": "Sale order not found"}
            order.write({"provider_code": provider_code})
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @http.route(
        "/shop/update_order_line_payment_fees", type="json", auth="public", website=True
    )
    # These controller is used to get the sale order, provider details, product details & do the calculation  of payment fee and apply into backend sale order and website amount summary
    def update_order_line_payment_fees(self, order_id, provider_code, **kwargs):
        order = request.env["sale.order"].sudo().browse(order_id)
        provider = (
            request.env["payment.provider"]
            .sudo()
            .search([("code", "=", provider_code)], limit=1)
        )

        if not order.exists() or not provider.exists():
            return {"success": False, "error": "Invalid order or provider"}

        try:
            # Find the 'Payment Fee' product
            payment_fee_product = (
                request.env["product.product"]
                .sudo()
                .search([("name", "=", "Payment Fee")], limit=1)
            )
            if not payment_fee_product:
                return {
                    "success": False,
                    "error": 'No "Payment Fee" product found in system',
                }

            # Filter real product lines (non-delivery, non-Payment Fee)
            real_product_lines = order.order_line.filtered(
                lambda l: not l.is_delivery and l.product_id != payment_fee_product
            )

            # Calculate total_base
            total_base = sum(line.price_unit for line in real_product_lines)

            # Handle conditional logic
            if provider.is_applied_on_condition:
                if provider.payment_fee_applied_on == "less":
                    if total_base < provider.amount_fee:
                        # Calculate payment fee based on type
                        payment_fee = 0.0
                        if provider.payment_fee_type == "fix":
                            payment_fee = provider.payment_fee or 0.0
                        elif provider.payment_fee_type == "percent":
                            percent = provider.payment_fee_percent * 100 or 0.0
                            payment_fee = (total_base * percent) / 100

                        # Add or update payment fee line
                        fee_line = order.order_line.filtered(
                            lambda l: l.product_id.id == payment_fee_product.id
                        )
                        if fee_line:
                            fee_line.write({"price_unit": payment_fee})
                        else:
                            request.env["sale.order.line"].sudo().create(
                                {
                                    "order_id": order.id,
                                    "product_id": payment_fee_product.id,
                                    "name": payment_fee_product.name,
                                    "product_uom_qty": 1,
                                    "price_unit": payment_fee,
                                    "tax_id": None,
                                }
                            )
                            order.amount_untaxed = order.amount_untaxed - payment_fee
                            order.amount_total = (
                                payment_fee + order.amount_untaxed + order.amount_tax
                            )
                    else:
                        # Remove fee line if condition not met
                        fee_line = order.order_line.filtered(
                            lambda l: l.product_id.id == payment_fee_product.id
                        )
                        if fee_line:
                            fee_line.unlink()
                elif provider.payment_fee_applied_on == "greater":
                    if total_base > provider.amount_fee:
                        # Calculate payment fee based on type
                        payment_fee = 0.0
                        if provider.payment_fee_type == "fix":
                            payment_fee = provider.payment_fee or 0.0
                        elif provider.payment_fee_type == "percent":
                            percent = provider.payment_fee_percent * 100 or 0.0
                            payment_fee = (total_base * percent) / 100

                        # Add or update payment fee line
                        fee_line = order.order_line.filtered(
                            lambda l: l.product_id.id == payment_fee_product.id
                        )
                        if fee_line:
                            fee_line.write({"price_unit": payment_fee})
                        else:
                            request.env["sale.order.line"].sudo().create(
                                {
                                    "order_id": order.id,
                                    "product_id": payment_fee_product.id,
                                    "name": payment_fee_product.name,
                                    "product_uom_qty": 1,
                                    "price_unit": payment_fee,
                                    "tax_id": None,
                                }
                            )
                            order.amount_untaxed = order.amount_untaxed - payment_fee
                            order.amount_total = (
                                payment_fee + order.amount_untaxed + order.amount_tax
                            )
                    else:
                        # Remove fee line if condition not met
                        fee_line = order.order_line.filtered(
                            lambda l: l.product_id.id == payment_fee_product.id
                        )
                        if fee_line:
                            fee_line.unlink()

                # Return early since condition logic handled
                order_lines_data = [
                    {
                        "id": line.id,
                        "product_name": line.product_id.name,
                        "price_unit": line.price_unit,
                    }
                    for line in order.order_line
                ]
                return {
                    "success": True,
                    "message": "Conditional logic applied (less)",
                    "order_lines": order_lines_data,
                    "amount_total": order.amount_total,
                }

            # Default logic if is_applied_on_condition is False
            payment_fee = 0.0

            if provider.payment_fee_type == "fix":
                payment_fee = provider.payment_fee or 0.0
            elif provider.payment_fee_type == "percent":
                percent = provider.payment_fee_percent * 100 or 0.0
                payment_fee = (total_base * percent) / 100

            fee_line = order.order_line.filtered(
                lambda l: l.product_id.id == payment_fee_product.id
            )

            if not real_product_lines:
                if fee_line:
                    fee_line.unlink()
            else:
                if fee_line:
                    fee_line.write({"price_unit": payment_fee})
                else:
                    request.env["sale.order.line"].sudo().create(
                        {
                            "order_id": order.id,
                            "product_id": payment_fee_product.id,
                            "name": payment_fee_product.name,
                            "product_uom_qty": 1,
                            "price_unit": payment_fee,
                            "tax_id": None,
                        }
                    )

            order_lines_data = [
                {
                    "id": line.id,
                    "product_name": line.product_id.name,
                    "price_unit": line.price_unit,
                }
                for line in order.order_line
            ]
            order.amount_untaxed = order.amount_untaxed - payment_fee
            order.amount_total = payment_fee + order.amount_untaxed + order.amount_tax

            return {
                "success": True,
                "payment_fee": payment_fee,
                "amount_total": order.amount_total,
                "order_lines": order_lines_data,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    @http.route("/shop/payment", type="http", auth="public", website=True)
    def shop_payment(self, **kwargs):
        # These controller will set the updated payment fee value in payment method
        # --- Call super method ---
        response = super(PaymentFeesController, self).shop_payment(**kwargs)

        # --- Get current sale order ---
        sale_order = request.website.sale_get_order()
        if not sale_order or not sale_order.order_line:
            return response  # no order or no lines, skip

        # Get the 'Payment Fee' product
        payment_fee_product = (
            request.env["product.product"]
            .sudo()
            .search([("name", "=", "Payment Fee")], limit=1)
        )

        # --- Get all active payment providers (enabled or test) ---
        active_providers = request.env["payment.provider"].search(
            [("state", "in", ["enabled", "test"])]
        )

        fee_line = sale_order.order_line.filtered(
            lambda l: l.product_id.id == payment_fee_product.id
        )
        real_product_lines = sale_order.order_line.filtered(
            lambda l: not l.is_delivery and l.product_id != payment_fee_product
        )

        if not real_product_lines:
            # If no real products, remove Payment Fee line if exists
            if fee_line:
                fee_line.unlink()

        # Loop over active providers
        for provider in active_providers:
            if provider.payment_fee_type == "percent":
                percent = provider.payment_fee_percent * 100 or 0.0
                total_base = 0.0

                # Sum price_unit of relevant lines (excluding delivery & payment fee product & services)
                for line in sale_order.order_line.filtered(
                    lambda l: not l.is_delivery and l.product_id != payment_fee_product
                ):
                    total_base += line.price_unit

                # Calculate the percent fee
                provider.calculated_payment_fee_percent = (total_base * percent) / 100

        return response
