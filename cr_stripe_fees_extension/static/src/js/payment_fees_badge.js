import paymentForm from '@payment/js/payment_form';

paymentForm.include({
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        await this._super(...arguments);
        
        if (providerCode !== 'stripe') {
            return;
        }

        // Handle both tokens and payment methods
        const radio = document.querySelector('input[name="o_payment_radio"]:checked');
        const paymentOptionType = radio?.dataset.paymentOptionType;

        // Fetch provider configuration
        const providerData = await this._fetchProviderConfig();
        if (!providerData) return;

        // Fetch country data
        const { companyCountryId, deliveryCountryId } = await this._fetchCountryData(providerData);
        
        // Calculate fees
        if (providerData.is_extra_fees == true) {
            const baseAmount = parseFloat(this.paymentContext.amount || 0);
            const calculatedFees = this._calculateFees(
                baseAmount,
                providerData,
                companyCountryId,
                deliveryCountryId
            );

            if (paymentOptionType === 'token') {
                // Handle saved token
                this._displayTokenFeeBadge(radio, calculatedFees, providerData);
            }
//            else {
//                // Handle payment method (existing logic)
//                this._displayPaymentMethodFeeBadge(radio, calculatedFees);
//            }
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

    async _fetchCountryData(provider) {
        let companyCountryId = null;
        let deliveryCountryId = null;

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

        // Fetch delivery country
        const orderId = this._extractOrderId();
        if (orderId) {
            try {
                const response = await fetch(`/custom/stripe/order_shipping_country/${orderId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({}),
                });
                const orderData = await response.json();
                deliveryCountryId = orderData.result?.country_id || null;
            } catch (error) {
                console.error('[Stripe Badge] Failed to fetch delivery country:', error);
            }
        }

        return { companyCountryId, deliveryCountryId };
    },

    _extractOrderId() {
        if (this.paymentContext.transactionRoute) {
            const matches = this.paymentContext.transactionRoute.match(/\/transaction\/(\d+)/);
            return matches?.[1] ? parseInt(matches[1]) : null;
        }
        return null;
    },

    _calculateFees(baseAmount, provider, companyCountryId, deliveryCountryId) {
        const isInternational = deliveryCountryId && companyCountryId && 
                                deliveryCountryId !== companyCountryId;

        let totalFixedFees = 0;
        let totalPercentFees = 0;

        if (isInternational) {
            if (!provider.is_free_international) {
                totalFixedFees = provider.fix_international_fees || 0;
                totalPercentFees = (provider.var_international_fees || 0) * baseAmount / 100;
            } else if (baseAmount < (provider.free_international_amount || 0)) {
                totalFixedFees = provider.fix_international_fees || 0;
                totalPercentFees = (provider.var_international_fees || 0) * baseAmount / 100;
            }
        } else {
            if (!provider.is_free_domestic) {
                totalFixedFees = provider.fix_domestic_fees || 0;
                totalPercentFees = (provider.var_domestic_fees || 0) * baseAmount / 100;
            } else if (baseAmount < (provider.free_domestic_amount || 0)) {
                totalFixedFees = provider.fix_domestic_fees || 0;
                totalPercentFees = (provider.var_domestic_fees || 0) * baseAmount / 100;
            }
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

        // Get currency symbol from payment context or provider
        const currencySymbol = this.paymentContext.currencySymbol || '$';

        // Clear existing content
        badgeContainer.innerHTML = '';
        badgeContainer.classList.remove('d-none');

        // Add fee badge
        const badge = document.createElement('span');
        badge.className = 'badge bg-primary ms-2';
        badge.style.fontSize = '11px';
        badge.style.padding = '3px 8px';
        badge.textContent = `+ ${currencySymbol}${calculatedFees.toFixed(2)} Fees`;
        
        badgeContainer.appendChild(badge);
        console.log('[Stripe Badge] Token fee badge displayed:', calculatedFees);
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
        const existingBadge = stripeInlineForm.querySelector('.stripe-fees-badge');
        if (existingBadge) existingBadge.remove();

        // Get currency symbol
        const stripeInlineFormValues = JSON.parse(
            stripeInlineForm.dataset['stripeInlineFormValues']
        );
        const currencySymbol = stripeInlineFormValues.currency_symbol || '$';

        // Create new badge
        const badgeDiv = document.createElement("div");
        badgeDiv.className = 'stripe-fees-badge';
        badgeDiv.innerHTML = `<span class="badge bg-primary" style="font-size:12px; padding:3px 6px;">+ ${currencySymbol}${calculatedFees.toFixed(2)} Fees</span>`;
        badgeDiv.style.position = "absolute";
        badgeDiv.style.zIndex = "9999";
        badgeDiv.style.pointerEvents = "none";

        stripeInlineForm.style.position = "relative";
        stripeInlineForm.appendChild(badgeDiv);

        // Position badge
        const updateBadgePosition = () => {
            const rect = iframe.getBoundingClientRect();
            const parentRect = stripeInlineForm.getBoundingClientRect();
            badgeDiv.style.top = rect.top - parentRect.top + 90 + "px";
            badgeDiv.style.left = rect.left - parentRect.left + 130 + "px";
            requestAnimationFrame(updateBadgePosition);
        };

        updateBadgePosition();
        console.log('[Stripe Badge] Payment method badge displayed:', calculatedFees);
    },
});