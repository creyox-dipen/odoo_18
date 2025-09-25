/** @odoo-module */
//
//import paymentForm from '@payment/js/payment_form';
//import { rpc } from "@web/core/network/rpc";
//
//paymentForm.include({
//
//    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
//        await this._super(...arguments);
//
//        if (providerCode !== 'stripe') return;
//
//        const radio = document.querySelector('input[name="o_payment_radio"]:checked');
//        const inlineForm = this._getInlineForm(radio);
//        const stripeInlineForm = inlineForm.querySelector('[name="o_stripe_element_container"]');
//        if (!stripeInlineForm) return;
//
//        // === Fetch Stripe provider configuration via RPC ===
//        let providerData = {};
//        try {
//            providerData = await rpc('/web/dataset/call_kw', {
//                model: 'payment.provider',
//                method: 'search_read',
//                args: [[['code', '=', 'stripe']]],
//                kwargs: {
//                    fields: [
//                        'is_extra_fees',
//                        'is_free_domestic',
//                        'is_free_international',
//                        'free_domestic_amount',
//                        'free_international_amount',
//                        'fix_domestic_fees',
//                        'var_domestic_fees',
//                        'fix_international_fees',
//                        'var_international_fees',
//                        'company_id'
//                    ],
//                    limit: 1,
//                },
//            });
//        } catch (e) {
//            console.error("[Stripe Badge] Could not fetch Stripe provider configuration:", e);
//        }
//
//        const provider = providerData.length ? providerData[0] : {};
//        if (!provider || !provider.company_id) return;
//
//        // === Get company country via RPC ===
//        let companyCountryId = null;
//        try {
//            const companyData = await rpc('/web/dataset/call_kw', {
//                model: 'res.company',
//                method: 'read',
//                args: [[provider.company_id[0]], ['country_id']],
//                kwargs: {},
//            });
//            companyCountryId = companyData[0].country_id ? companyData[0].country_id[0] : null;
//        } catch (e) {
//            console.error("[Stripe Badge] Could not fetch company data:", e);
//        }
//
//
//
//        // === Add sticky badge ===
//        function addStickyBadge() {
//            const iframe = stripeInlineForm.querySelector("iframe");
//            if (!iframe) return;
//            let stripeInlineFormValues = JSON.parse(
//                        stripeInlineForm.dataset['stripeInlineFormValues']
//                    );
//            let fees = stripeInlineFormValues.fees
//            const badgeDiv = document.createElement("div");
//            badgeDiv.innerHTML = `<span class="badge bg-primary">+  ${stripeInlineFormValues.currency_symbol}${fees} Fees</span>`;
//            badgeDiv.style.position = "absolute";
//            badgeDiv.style.zIndex = "9999";
//            badgeDiv.style.pointerEvents = "none";
//
//            stripeInlineForm.style.position = "relative";
//            stripeInlineForm.appendChild(badgeDiv);
//
//            function updateBadgePosition() {
//                const rect = iframe.getBoundingClientRect();
//                const parentRect = stripeInlineForm.getBoundingClientRect();
//                badgeDiv.style.top = rect.top - parentRect.top + 90 + "px";
//                badgeDiv.style.left = rect.left - parentRect.left + 130 + "px";
//                requestAnimationFrame(updateBadgePosition);
//            }
//
//            updateBadgePosition();
//        }
//
//        setTimeout(addStickyBadge, 1500);
//    },
//});


import paymentForm from '@payment/js/payment_form';
import { rpc } from "@web/core/network/rpc";

paymentForm.include({

    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        await this._super(...arguments);

        if (providerCode !== 'stripe') return;

        const radio = document.querySelector('input[name="o_payment_radio"]:checked');
        const inlineForm = this._getInlineForm(radio);
        const stripeInlineForm = inlineForm.querySelector('[name="o_stripe_element_container"]');
        if (!stripeInlineForm) return;

        // === Fetch Stripe provider configuration via RPC ===
        let providerData = {};
        try {
            providerData = await rpc('/web/dataset/call_kw', {
                model: 'payment.provider',
                method: 'search_read',
                args: [[['code', '=', 'stripe']]],
                kwargs: {
                    fields: [
                        'is_extra_fees',
                        'is_free_domestic',
                        'is_free_international',
                        'free_domestic_amount',
                        'free_international_amount',
                        'fix_domestic_fees',
                        'var_domestic_fees',
                        'fix_international_fees',
                        'var_international_fees',
                        'company_id'
                    ],
                    limit: 1,
                },
            });
        } catch (e) {
            console.error("[Stripe Badge] Could not fetch Stripe provider configuration:", e);
        }

        const provider = providerData.length ? providerData[0] : {};
        if (!provider || !provider.company_id) return;

        // === Get company country via RPC ===
        let companyCountryId = null;
        try {
            const companyData = await rpc('/web/dataset/call_kw', {
                model: 'res.company',
                method: 'read',
                args: [[provider.company_id[0]], ['country_id']],
                kwargs: {},
            });
            console.log(companyData)
            companyCountryId = companyData[0].country_id ? companyData[0].country_id[0] : null;
        } catch (e) {
            console.error("[Stripe Badge] Could not fetch company data:", e);
        }

        let stripeInlineFormValues = JSON.parse(
                        stripeInlineForm.dataset['stripeInlineFormValues']
                    );
        console.log(stripeInlineFormValues)

        // === Add sticky badge ===
        function addStickyBadge() {
            const iframe = stripeInlineForm.querySelector("iframe");
            if (!iframe) return;
            let stripeInlineFormValues = JSON.parse(
                        stripeInlineForm.dataset['stripeInlineFormValues']
                    );
            let fees = stripeInlineFormValues.fees
            const badgeDiv = document.createElement("div");
            badgeDiv.innerHTML = `<span class="badge bg-primary" style="font-size:12px; padding:3px 6px;">+ ${stripeInlineFormValues.currency_symbol}${fees} Fees</span>`;
            badgeDiv.style.position = "absolute";
            badgeDiv.style.zIndex = "9999";
            badgeDiv.style.pointerEvents = "none";

            stripeInlineForm.style.position = "relative";
            stripeInlineForm.appendChild(badgeDiv);

            function updateBadgePosition() {
                const rect = iframe.getBoundingClientRect();
                const parentRect = stripeInlineForm.getBoundingClientRect();
                badgeDiv.style.top = rect.top - parentRect.top + 90 + "px";
                badgeDiv.style.left = rect.left - parentRect.left + 130 + "px";
                requestAnimationFrame(updateBadgePosition);
            }

            updateBadgePosition();
        }

        setTimeout(addStickyBadge, 1500);
    },
});