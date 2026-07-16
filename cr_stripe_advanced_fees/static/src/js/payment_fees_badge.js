/** @odoo-module **/

function wrapStripe(StripeLib) {
    return function (publishableKey, options) {
        const stripeInstance = StripeLib(publishableKey, options);
        if (!stripeInstance) {
            return stripeInstance;
        }
        return new Proxy(stripeInstance, {
            get(target, prop, receiver) {
                if (prop === 'elements') {
                    return function (elementsOptions) {
                        if (elementsOptions && elementsOptions.mode === 'payment') {
                            elementsOptions.paymentMethodCreation = 'manual';
                        }
                        return target.elements.call(target, elementsOptions);
                    };
                }
                const value = Reflect.get(target, prop, receiver);
                if (typeof value === 'function') {
                    return value.bind(target);
                }
                return value;
            }
        });
    };
}

if (window.Stripe) {
    window.Stripe = wrapStripe(window.Stripe);
} else {
    let originalStripe = undefined;
    Object.defineProperty(window, 'Stripe', {
        get() {
            return originalStripe;
        },
        set(val) {
            originalStripe = wrapStripe(val);
        },
        configurable: true,
    });
}

import paymentForm from '@payment/js/payment_form';
import { rpc } from "@web/core/network/rpc";

paymentForm.include({
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        await this._super(...arguments);
        if (providerCode !== 'stripe') {
            return;
        }
        this.detectedBrand = null;

        // Handle both tokens and payment methods
        const radio = document.querySelector('input[name="o_payment_radio"]:checked');
        const paymentOptionType = radio?.dataset.paymentOptionType;
        // Determine method code
        let methodCode = paymentMethodCode;
        if (paymentOptionType === 'token') {
            // Fetch token-specific method code (defaults to 'card' for Stripe tokens)
            const tokenId = radio.dataset.paymentOptionId;
            const tokenData = await this._fetchTokenMethod(tokenId);
            methodCode = tokenData?.payment_method_code || '';
        }

        // Fetch provider configuration
        const providerData = await this._fetchProviderConfig();
        if (!providerData || !providerData.line_ids) return;
        // Fetch country data
        const { companyCountryId, partnerCountryId } = await this._fetchCountryData(providerData);
        // Calculate fees
        if (providerData.is_extra_fees == true) {
            const rawAmount = this.el?.getAttribute('data-amount') || this.paymentContext.amount;
            const baseAmount = this._parseAmount(rawAmount);
            const calculatedFees = this._calculateFees(
                baseAmount,
                providerData,
                companyCountryId,
                partnerCountryId,
                methodCode
            );

            if (paymentOptionType === 'token') {
                // Handle saved token (brand is already known)
                this._displayTokenFeeBadge(radio, calculatedFees, providerData);
            } else if (paymentMethodCode !== 'card') {
                // For non-card static payment methods (like ACH), display the badge immediately
                this._displayPaymentMethodFeeBadge(radio, calculatedFees);
            } else {
                // For new cards, clear any initial default fee badge so it remains hidden initially
                const inlineForm = this._getInlineForm(radio);
                const stripeInlineForm = inlineForm?.querySelector('[name="o_stripe_element_container"]');
                const existingBadge = inlineForm?.querySelector('.stripe-fees-badge');
                if (existingBadge) existingBadge.remove();

                const paymentElement = this.stripeElements[paymentOptionId]?.getElement('payment');
                if (paymentElement) {
                    paymentElement.on('change', async (event) => {
                        const currentRawAmount = this.el?.getAttribute('data-amount') || this.paymentContext.amount;
                        const currentBaseAmount = this._parseAmount(currentRawAmount);

                        if (event.complete) {
                            try {
                                const { error: submitError } = await this.stripeElements[paymentOptionId].submit();
                                if (submitError) {
                                    console.warn('[Stripe Badge] submit error:', submitError);
                                    return;
                                }
                                const result = await this.stripeJS.createPaymentMethod({
                                    elements: this.stripeElements[paymentOptionId],
                                });
                                if (result.paymentMethod && result.paymentMethod.card) {
                                    const brand = (result.paymentMethod.card.brand || '').toLowerCase();
                                    this.detectedBrand = brand;

                                    const updatedFees = this._calculateFees(
                                        currentBaseAmount,
                                        providerData,
                                        companyCountryId,
                                        partnerCountryId,
                                        brand
                                    );
                                    this._displayPaymentMethodFeeBadge(radio, updatedFees);
                                }
                            } catch (e) {
                                console.error('[Stripe Badge] Error tokenizing card for brand detection:', e);
                            }

                        } else {
                            // Reset if details are modified/incomplete
                            this.detectedBrand = null;
                            const badge = inlineForm?.querySelector('.stripe-fees-badge');
                            if (badge) badge.remove();
                        }
                    });
                }
            }
        }
    },
    async _fetchProviderConfig() {
        try {
            const response = await fetch('/custom/stripe/provider_config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            });
            const data = await response.json();
            const provider = data.result || {};
            if (!provider || !provider.company_id) {
                console.warn('[Stripe Badge] No provider or missing company_id');
                return null;
            }
            return provider;
        } catch (e) {
            console.error('[Stripe Badge] Could not fetch provider config:', e);
            return null;
        }
    },
    async _fetchTokenMethod(tokenId) {
        try {
            const response = await fetch(`/custom/stripe/token_method/${tokenId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            });
            const data = await response.json();

            // handle both shapes: { result: { ... } } or { payment_method_code: 'visa' }
            const payload = data.result || data || {};
            const code = payload.payment_method_code || payload.payment_method || payload.code || null;

            // normalize to lower case if present
            if (code) {
                return { payment_method_code: String(code).toLowerCase() };
            }
            return {};
        } catch (e) {
            console.error('[Stripe Badge] Could not fetch token method:', e);
            return {};
        }
    },

    async _fetchCountryData(provider) {
        let companyCountryId = null;
        let partnerCountryId = null;
        // Fetch company country
        try {
            const response = await fetch(`/custom/stripe/company_country/${provider.company_id[0] || provider.company_id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            });
            const companyData = await response.json();
            companyCountryId = companyData.result?.country_id || null;
        } catch (e) {
            console.error('[Stripe Badge] Could not fetch company country:', e);
        }
        // Fetch partner (billing) country
        const orderId = this._extractOrderId();
        const url = orderId 
            ? `/custom/stripe/order_partner_country/${orderId}` 
            : `/custom/stripe/order_partner_country`;
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            });
            const orderData = await response.json();
            partnerCountryId = orderData.result?.country_id || null;
        } catch (error) {
            console.error('[Stripe Badge] Failed to fetch partner country:', error);
        }
        return { companyCountryId, partnerCountryId };
    },
    _extractOrderId() {
        if (this.paymentContext.transactionRoute) {
            const matches = this.paymentContext.transactionRoute.match(/\/transaction\/(\d+)/);
            return matches?.[1] ? parseInt(matches[1]) : null;
        }
        return null;
    },
    _parseAmount(amount) {
        if (amount === undefined || amount === null) {
            return 0;
        }
        if (typeof amount === 'number') {
            return amount;
        }
        let cleaned = String(amount).replace(/[^\d.,-]/g, '');
        if (cleaned.includes(',') && cleaned.includes('.')) {
            cleaned = cleaned.replace(/,/g, '');
        } else if (cleaned.includes(',')) {
            if (cleaned.match(/,\d{2}$/)) {
                cleaned = cleaned.replace(/,/g, '.');
            } else {
                cleaned = cleaned.replace(/,/g, '');
            }
        }
        const parsed = parseFloat(cleaned);
        return isNaN(parsed) ? 0 : parsed;
    },
    _calculateFees(baseAmount, providerData, companyCountryId, partnerCountryId, methodCode) {
        const isInternational = partnerCountryId && companyCountryId && partnerCountryId !== companyCountryId;
        const mcode = (methodCode || '').toLowerCase();

        // Try perfect match
        let feeLine = providerData.line_ids.find(
            line => (line.payment_method_code || '').toLowerCase() === mcode
        );

        // Fallback to default method if no specific match
        if (!feeLine) {
            feeLine = providerData.line_ids.find(line => line.default_method);
        }

        if (!feeLine) {
            return 0;
        }
        let totalFixedFees = 0;
        let totalPercentFees = 0;
        let feeTypeFree, feeTypeFixed, feeTypeVar, feeTypeThreshold;
        if (isInternational) {
            feeTypeFree = feeLine.is_free_international;
            feeTypeFixed = feeLine.fix_international_fees || 0;
            feeTypeVar = feeLine.var_international_fees || 0;
            feeTypeThreshold = feeLine.free_international_amount || 0;
        } else {
            feeTypeFree = feeLine.is_free_domestic;
            feeTypeFixed = feeLine.fix_domestic_fees || 0;
            feeTypeVar = feeLine.var_domestic_fees || 0;
            feeTypeThreshold = feeLine.free_domestic_amount || 0;
        }
        const applyFees = !feeTypeFree || baseAmount < feeTypeThreshold;
        if (applyFees) {
            totalFixedFees = feeTypeFixed;
            totalPercentFees = (feeTypeVar * baseAmount) / 100;
        }
        return Math.round((totalFixedFees + totalPercentFees) * 100) / 100;
    },
    _displayTokenFeeBadge(radio, calculatedFees, providerData) {
        const tokenId = radio.dataset.paymentOptionId;
        const badgeContainer = document.querySelector(
            `.stripe-token-fees-badge[data-token-id="${tokenId}"]`
        );

        if (!badgeContainer) {
            console.warn('[Stripe Badge] Token badge container not found');
            return;
        }

        if (calculatedFees <= 0) {
            badgeContainer.classList.add('d-none');
            return;
        }

        const currencyId = parseInt(this.paymentContext.currencyId);

        rpc('/web/dataset/call_kw', {
            model: 'res.currency',
            method: 'read',
            args: [[currencyId], ['symbol']],
            kwargs: {},
            context: {},
        }).then(result => {
            const currencySymbol = result?.[0]?.symbol || '$';

            badgeContainer.innerHTML = '';
            badgeContainer.classList.remove('d-none');

            const badge = document.createElement('span');
            badge.className = 'badge bg-primary ms-2';
            badge.style.fontSize = '11px';
            badge.style.padding = '3px 8px';
            badge.textContent = `+ ${currencySymbol}${calculatedFees.toFixed(2)} Fees`;

            badgeContainer.appendChild(badge);
        });
    },

    _displayPaymentMethodFeeBadge(radio, calculatedFees) {
        const inlineForm = this._getInlineForm(radio);
        const stripeInlineForm = inlineForm?.querySelector('[name="o_stripe_element_container"]');
        if (!stripeInlineForm) return;
        const iframe = stripeInlineForm.querySelector("iframe");
        if (!iframe) {
            console.warn('[Stripe Badge] Iframe not found for payment method');
            return;
        }
        const iframeSrc = iframe.src || iframe.getAttribute('src') || '';
        const hasPrefilledCountry = iframeSrc.includes('publicOptions[defaultValues][billingDetails][address][country]=');
        if (!hasPrefilledCountry) {
            console.log('[Stripe Badge] Country selection enabled, skipping badge');
            return;
        }
        // Remove existing badge
        const existingBadge = inlineForm.querySelector('.stripe-fees-badge');
        if (existingBadge) existingBadge.remove();

        if (calculatedFees <= 0) {
            console.log('[Stripe Badge] Payment method badge skipped (fees <= 0):', calculatedFees);
            return;
        }

        // Get currency symbol
        const stripeInlineFormValues = JSON.parse(
            stripeInlineForm.dataset['stripeInlineFormValues']
        );
        const currencySymbol = stripeInlineFormValues.currency_symbol || '$';
        // Create badge as a normal block element and insert it directly after the stripe container
        // so it sits in the natural gap between the Stripe form and the "Secured by Stripe" row
        const badgeDiv = document.createElement('div');
        badgeDiv.className = 'stripe-fees-badge mt-2';
        badgeDiv.innerHTML = `<span class="badge bg-primary" style="font-size:12px; padding:3px 6px;">+ ${currencySymbol}${calculatedFees.toFixed(2)} Fees</span>`;
        stripeInlineForm.insertAdjacentElement('afterend', badgeDiv);

        console.log('[Stripe Badge] Payment method badge displayed:', calculatedFees);
    },

    _prepareTransactionRouteParams() {
        const params = this._super(...arguments);
        if (this.detectedBrand) {
            params.stripe_card_brand = this.detectedBrand;
        }
        return params;
    },

});