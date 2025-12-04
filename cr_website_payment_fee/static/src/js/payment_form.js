/** @odoo-module **/
import { rpc } from "@web/core/network/rpc";
import publicWidget from "@web/legacy/js/public/public_widget";

const PaymentForm = publicWidget.registry.PaymentForm;

PaymentForm.include({
    start() {
        console.log("start method called");
        this._super(...arguments);
        console.log("super method called");

        const storedPaymentOptionId = sessionStorage.getItem('o_payment_form');
        console.log("storedPaymentOptionId:", storedPaymentOptionId);

        if (storedPaymentOptionId) {
            const $storedRadio = this.$(`input[name="o_payment_radio"][data-payment-option-id="${storedPaymentOptionId}"]`);
            console.log("$storedRadio found:", $storedRadio.length > 0);
            if ($storedRadio.length) {
                $storedRadio.prop('checked', true);
                console.log("Radio input set to checked");
            }
            sessionStorage.removeItem('o_payment_form');
            console.log("o_payment_form removed from sessionStorage");
        }

        this._fetchSaleOrder().then((orderData) => {
            console.log("Sale order fetched:", orderData);
            this.saleOrder = orderData;
        }).catch((err) => {
            console.error("Error fetching sale order:", err);
        });

        this.$el.on('change', 'input[name="o_payment_radio"]', (ev) => {
            console.log("Payment radio changed");
            const $radio = $(ev.currentTarget);
            const paymentOptionId = $radio.data('payment-option-id');
            const providerCode = $radio.data('provider-code');
            const paymentFeeType = $radio.data('payment-fee-type');
            const paymentFeePercent = parseFloat($radio.data('payment-fee-percent')) || 0;

            console.log("Selected payment option:", { paymentOptionId, providerCode, paymentFeeType, paymentFeePercent });

            if (this.saleOrder) {
                console.log("Sale order available:", this.saleOrder.id);
                sessionStorage.setItem('o_payment_form', paymentOptionId);
                console.log("o_payment_form set in sessionStorage");

                let calculatedFee = 0;
                if (paymentFeeType === 'percent') {
                    calculatedFee = (this.saleOrder.amount_total * paymentFeePercent) / 100;
                    console.log("Calculated fee (percent):", calculatedFee);
                }

                this._updateOrderLinePaymentFees(this.saleOrder.id, providerCode, paymentFeeType, calculatedFee).then((result) => {
                    console.log("Order line updated:", result);
                    if (result.success) {
                        console.log("Reloading page...");
                        window.location.reload();
                    }
                }).catch((err) => {
                    console.error("Error updating order line:", err);
                });
            } else {
                console.warn("No sale order available during payment option change");
            }
        });

        return Promise.resolve();
    },

    async _fetchSaleOrder() {
        console.log("_fetchSaleOrder called");
        return rpc('/shop/get_order_data', {}).then((result) => {
            console.log("get_order_data result:", result);
            if (result && result.order) {
                return result.order;
            } else {
                throw new Error('No sale order found');
            }
        });
    },

    async _updateOrderLinePaymentFees(orderId, providerCode, paymentFeeType, calculatedFee) {
        console.log("_updateOrderLinePaymentFees called with:", {
            orderId,
            providerCode,
            paymentFeeType,
            calculatedFee,
        });
        return rpc('/shop/update_order_line_payment_fees', {
            order_id: orderId,
            provider_code: providerCode,
            payment_fee_type: paymentFeeType,
            calculated_fee: calculatedFee,
        }).then((result) => {
            console.log("update_order_line_payment_fees result:", result);
            if (result.success) {
                return result;
            } else {
                throw new Error(result.error);
            }
        });
    },
});

export default PaymentForm;