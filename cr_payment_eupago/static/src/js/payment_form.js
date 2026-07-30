/** @odoo-module **/

import paymentForm from '@payment/js/payment_form';
import { rpc, RPCError } from '@web/core/network/rpc';
import { _t } from "@web/core/l10n/translation";

paymentForm.include({
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode !== 'eupago_mbway') {
            await this._super(...arguments);
            return;
        } else if (flow === 'token') {
            return;
        }
        this._setPaymentFlow('direct');
    },

    async _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'eupago_mbway') {
            await this._super(...arguments);
            return;
        }

        const phoneInput = document.getElementById('cr_eupago_phone');
        const phone = phoneInput ? phoneInput.value.trim().replace(/\s+/g, '') : '';
        
        if (!phone || !/^[0-9]{9}$/.test(phone)) {
            this._displayErrorDialog(_t("Invalid Phone Number"), _t("Please enter a valid 9-digit phone number."));
            this._enableButton();
            return;
        }

        // Call our custom controller to process the MB WAY payment
        try {
            await rpc('/payment/cr_eupago/mbway/pay', {
                'reference': processingValues.reference,
                'phone': phone,
            });
            
            // Switch view to pending notification
            const container = document.querySelector('.o_cr_eupago_mbway_container');
            if (container) {
                const phoneForm = container.querySelector('.o_cr_eupago_mbway_phone_form');
                if (phoneForm) {
                    phoneForm.classList.add('d-none');
                }
                const pendingDiv = container.querySelector('.o_cr_eupago_mbway_pending');
                if (pendingDiv) {
                    pendingDiv.classList.remove('d-none');
                    const phoneStrong = pendingDiv.querySelector('strong');
                    if (phoneStrong) {
                        phoneStrong.textContent = phone;
                    }
                }
            }

            // Start polling for payment status
            this._eupagoPollMbwayStatus(processingValues.reference);

        } catch (error) {
            if (error instanceof RPCError) {
                this._displayErrorDialog(_t("Payment processing failed"), error.data.message);
                this._enableButton();
            } else {
                return Promise.reject(error);
            }
        }
    },

    _eupagoPollMbwayStatus(reference) {
        // Max 5 minutes (60 checks × 5 seconds). If the customer hasn't confirmed
        // by then, redirect to the status page showing the current state.
        const MAX_POLL_ATTEMPTS = 60;
        let attempts = 0;

        const pollInterval = setInterval(async () => {
            attempts++;

            // Hard timeout — stop polling after 5 minutes
            if (attempts >= MAX_POLL_ATTEMPTS) {
                clearInterval(pollInterval);
                console.debug('euPago MB WAY poll: timeout after ' + attempts + ' attempts for ref ' + reference);
                window.location = '/payment/status';
                return;
            }

            try {
                const response = await rpc('/payment/cr_eupago/mbway/status', {
                    'ref': reference,
                });
                if (response.state === 'done') {
                    clearInterval(pollInterval);
                    window.location = '/payment/status';
                } else if (response.state && response.state !== 'pending' && response.state !== 'draft') {
                    // error / cancel — also redirect to status page
                    clearInterval(pollInterval);
                    window.location = '/payment/status';
                }
            } catch (e) {
                // Ignore transient RPC errors during polling — keep retrying
            }
        }, 5000); // Poll every 5 seconds
    }
});
