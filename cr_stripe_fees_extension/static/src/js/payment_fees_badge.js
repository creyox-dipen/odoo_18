/** @odoo-module **/
 
import paymentForm from '@payment/js/payment_form';
 
paymentForm.include({
    /**
     * @override
     */
    async start() {
        await this._super(...arguments);
 
        // Initialize MutationObserver to detect payment context changes
        this._initPaymentContextObserver();
    },
 
    /**
     * Initialize observer to detect when payment amount changes in the DOM
     * This handles the case when user switches between "Next amount" and "Full amount"
     */
    _initPaymentContextObserver() {
        console.log('[Stripe Badge] 🚀 Initializing payment context observer...');
 
        // Store the current amount to detect changes
        this._lastObservedAmount = this._getSelectedAmount();
        console.log('[Stripe Badge] Initial amount:', this._lastObservedAmount);
 
        // Listen for clicks on amount selection buttons
        // Use document instead of this.el to catch clicks in the modal
        document.addEventListener('click', (event) => {
            console.log('[Stripe Badge] 🖱️ Click detected on:', event.target);
 
            // Check if click is on amount selection button or its parent
            const amountButton = event.target.closest('.o_btn_payment_tab') ||
                event.target.closest('[data-amount-type]') ||
                event.target.closest('.o_amount_button') ||
                event.target.closest('button[name="o_payment_amount"]');
 
            if (amountButton) {
                console.log('[Stripe Badge] ✅ Click is on amount button:', amountButton);
 
                // Small delay to let DOM update (Bootstrap tab transition)
                setTimeout(() => {
                    console.log('[Stripe Badge] ⏱️ Checking amount after 150ms delay...');
                    const newAmount = this._getSelectedAmount();
                    if (newAmount && newAmount !== this._lastObservedAmount) {
                        console.log('[Stripe Badge] 🔄 Amount changed from', this._lastObservedAmount, 'to', newAmount);
                        this._lastObservedAmount = newAmount;
                        this._updateStripeFees();
                    } else {
                        console.log('[Stripe Badge] ℹ️ Amount unchanged:', newAmount);
                    }
                }, 150); // Increased delay for Bootstrap tab animation
            } else {
                console.log('[Stripe Badge] ℹ️ Click not on amount button, ignoring');
            }
        });
 
        // Also use MutationObserver as fallback for class changes
        // Observe the modal and payment form
        const observeTarget = document.querySelector('#pay_with') || this.el;
 
        this._paymentContextObserver = new MutationObserver(() => {
            console.log('[Stripe Badge] 👁️ MutationObserver detected DOM change');
            const newAmount = this._getSelectedAmount();
            if (newAmount && newAmount !== this._lastObservedAmount) {
                console.log('[Stripe Badge] 🔄 Amount changed (via observer) from', this._lastObservedAmount, 'to', newAmount);
                this._lastObservedAmount = newAmount;
                this._updateStripeFees();
            }
        });
 
        // Observe the entire modal for class changes
        this._paymentContextObserver.observe(observeTarget, {
            attributes: true,
            attributeFilter: ['class'],
            subtree: true,
        });
 
        console.log('[Stripe Badge] ✅ Observer initialized successfully');
    },
 
    /**
     * Get the currently selected payment amount from the DOM
     * Looks for active/selected amount button and extracts the amount value
     */
    _getSelectedAmount() {
        console.log('[Stripe Badge] 🔍 Starting amount detection...');
 
        // Method 1: Look for active payment tab button (Installment/Full Amount)
        // Search in entire document since tabs are in modal
        console.log('[Stripe Badge] Method 1: Looking for .o_btn_payment_tab.active...');
        let selectedButton = document.querySelector('.o_btn_payment_tab.active');
 
        if (selectedButton) {
            console.log('[Stripe Badge] ✅ Method 1 SUCCESS - Found active payment tab:', selectedButton);
 
            // Extract amount from .oe_currency_value inside the button
            const currencyValueSpan = selectedButton.querySelector('.oe_currency_value');
            if (currencyValueSpan) {
                const amountText = currencyValueSpan.textContent.trim();
                console.log('[Stripe Badge] Found .oe_currency_value with text:', amountText);
 
                const amount = parseFloat(amountText.replace(/,/g, ''));
                console.log('[Stripe Badge] 🎯 FINAL AMOUNT from active tab:', amount);
                return amount;
            } else {
                console.log('[Stripe Badge] ⚠️ No .oe_currency_value found in active tab');
            }
        } else {
            console.log('[Stripe Badge] ❌ Method 1 FAILED - No .o_btn_payment_tab.active found');
        }
 
        // Method 2: Look for active tab-pane and extract from amount display
        console.log('[Stripe Badge] Method 2: Looking for active .tab-pane...');
        const activeTabPane = document.querySelector('.tab-pane.active, .tab-pane.show.active');
 
        if (activeTabPane) {
            console.log('[Stripe Badge] ✅ Found active tab-pane:', activeTabPane.id);
 
            // Look for amount in the summary section
            const amountSpan = activeTabPane.querySelector('[id^="o_payment_summary_amount"] .oe_currency_value');
            if (amountSpan) {
                const amountText = amountSpan.textContent.trim();
                console.log('[Stripe Badge] Found amount in tab-pane:', amountText);
 
                const amount = parseFloat(amountText.replace(/,/g, ''));
                console.log('[Stripe Badge] 🎯 FINAL AMOUNT from tab-pane:', amount);
                return amount;
            }
        } else {
            console.log('[Stripe Badge] ❌ Method 2 FAILED - No active tab-pane found');
        }
 
        // Method 3: Check form data attributes based on active tab
        console.log('[Stripe Badge] Method 3: Checking form data attributes...');
        const paymentForm = document.querySelector('#o_payment_form') || this.el;
 
        // Check which tab is active to determine which amount to use
        const installmentTabActive = document.querySelector('#o_payment_installments_tab.active') ||
            document.querySelector('#o_payment_installments.active, #o_payment_installments.show.active');
 
        console.log('[Stripe Badge] Installment tab active?', !!installmentTabActive);
 
        if (installmentTabActive) {
            const nextAmount = paymentForm.dataset.invoiceNextAmountToPay;
            if (nextAmount) {
                const amount = parseFloat(nextAmount);
                console.log('[Stripe Badge] ✅ Method 3 SUCCESS - Using invoice-next-amount-to-pay:', amount);
                return amount;
            }
        } else {
            const fullAmount = paymentForm.dataset.amount || paymentForm.dataset.invoiceAmountDue;
            if (fullAmount) {
                const amount = parseFloat(fullAmount);
                console.log('[Stripe Badge] ✅ Method 3 SUCCESS - Using full amount:', amount);
                return amount;
            }
        }
 
        console.log('[Stripe Badge] ❌ Method 3 FAILED - No data attributes found');
 
        // Method 4: Fallback to any .oe_currency_value in visible area
        console.log('[Stripe Badge] Method 4: Looking for any visible .oe_currency_value...');
        const allCurrencyValues = document.querySelectorAll('.oe_currency_value');
        console.log('[Stripe Badge] Found', allCurrencyValues.length, '.oe_currency_value elements');
 
        for (const currencyValue of allCurrencyValues) {
            // Check if element is visible
            if (currencyValue.offsetParent !== null) {
                const amountText = currencyValue.textContent.trim();
                const amount = parseFloat(amountText.replace(/,/g, ''));
 
                if (!isNaN(amount) && amount > 0) {
                    console.log('[Stripe Badge] ✅ Method 4 SUCCESS - Found visible amount:', amount);
                    return amount;
                }
            }
        }
 
        console.log('[Stripe Badge] ❌ Method 4 FAILED - No visible amounts found');
 
        // Fallback: Try to get from payment context
        const fallbackAmount = parseFloat(this.paymentContext.amount || 0);
        console.log('[Stripe Badge] ⚠️ Using FALLBACK from paymentContext.amount:', fallbackAmount);
        return fallbackAmount;
    },
 
    /**
     * @override
     */
    destroy() {
        // Disconnect observer when widget is destroyed
        if (this._paymentContextObserver) {
            this._paymentContextObserver.disconnect();
        }
        this._super(...arguments);
    },
 
    /**
     * @override
     */
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        await this._super(...arguments);
 
        if (providerCode !== 'stripe') {
            return;
        }
 
        // Store provider data for later use
        if (!this._stripeProviderData) {
            this._stripeProviderData = await this._fetchProviderConfig();
        }
 
        if (!this._stripeProviderData) return;
 
        // Fetch country data once
        if (!this._stripeCountryData) {
            this._stripeCountryData = await this._fetchCountryData(this._stripeProviderData);
        }
 
        // Display initial fees
        await this._updateStripeFees();
    },
 
    /**
     * Update all Stripe fee badges based on current payment context
     */
    async _updateStripeFees() {
        const radio = document.querySelector('input[name="o_payment_radio"]:checked');
        if (!radio || radio.dataset.providerCode !== 'stripe') {
            return;
        }
 
        const providerData = this._stripeProviderData;
        const countryData = this._stripeCountryData;
 
        if (!providerData || !countryData || providerData.is_extra_fees !== true) {
            return;
        }
 
        // Get the current amount from the selected amount button in DOM
        const baseAmount = this._getSelectedAmount();
 
        console.log('[Stripe Badge] Calculating fees for amount:', baseAmount);
 
        // Calculate fees
        const calculatedFees = this._calculateFees(
            baseAmount,
            providerData,
            countryData.companyCountryId,
            countryData.deliveryCountryId
        );
 
        // Update badge based on payment option type
        const paymentOptionType = radio.dataset.paymentOptionType;
 
        if (paymentOptionType === 'token') {
            this._displayTokenFeeBadge(radio, calculatedFees, providerData);
        } else {
            this._displayPaymentMethodFeeBadge(radio, calculatedFees);
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
        console.log('[Stripe Badge] Token fee badge updated:', calculatedFees);
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
        console.log('[Stripe Badge] Payment method badge updated:', calculatedFees);
    },
});