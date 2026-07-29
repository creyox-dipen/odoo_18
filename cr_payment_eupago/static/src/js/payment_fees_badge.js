/** @odoo-module **/

import paymentForm from '@payment/js/payment_form';
import { rpc } from "@web/core/network/rpc";

paymentForm.include({
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {

        await this._super(...arguments);
        // Only process euPago providers
        if (!['eupago_cc', 'eupago_mbway', 'eupago_mbref'].includes(providerCode)) {
            return;
        }

        const radio = document.querySelector('input[name="o_payment_radio"]:checked');
        const paymentOptionType = radio?.dataset.paymentOptionType;

        // Fetch provider configuration
        const providerData = await this._fetchEupagoProviderConfig(providerCode);
        if (!providerData) return;

        // Fetch country data
        const { companyCountryId, deliveryCountryId } = await this._fetchEupagoCountryData(providerData);

        // Calculate fees
        if (providerData.cr_eupago_is_extra_fees == true) {
            const baseAmount = parseFloat(this.paymentContext.amount || 0);
            const calculatedFees = this._calculateEupagoFees(
                baseAmount,
                providerData,
                companyCountryId,
                deliveryCountryId
            );

            if (calculatedFees > 0) {
                this._displayEupagoFeeBadge(radio, calculatedFees, providerData);
            }
        }
    },

    async _fetchEupagoProviderConfig(providerCode) {
        try {
            const response = await fetch('/custom/eupago/provider_config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ params: { provider_code: providerCode } }),
            });
            const data = await response.json();
            const provider = data.result || {};

            if (!provider || !provider.company_id) {
                console.warn('[euPago Badge] No provider or missing company_id');
                return null;
            }
            return provider;
        } catch (e) {
            console.error('[euPago Badge] Could not fetch provider config:', e);
            return null;
        }
    },

    async _fetchEupagoCountryData(provider) {
        let companyCountryId = null;
        let deliveryCountryId = null;

        // Fetch company country
        try {
            const response = await fetch(`/custom/eupago/company_country/${provider.company_id[0] || provider.company_id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ params: {} }),
            });
            const companyData = await response.json();
            companyCountryId = companyData.result?.country_id || null;
        } catch (e) {
            console.error('[euPago Badge] Could not fetch company country:', e);
        }

        // Fetch delivery country
        const { docId, isInvoice } = this._extractEupagoDocumentInfo();
        if (docId) {
            try {
                const response = await fetch(`/custom/eupago/document_shipping_country/${docId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ params: { is_invoice: isInvoice } }),
                });
                const docData = await response.json();
                deliveryCountryId = docData.result?.country_id || null;
            } catch (error) {
                console.error('[euPago Badge] Failed to fetch delivery country:', error);
            }
        }

        return { companyCountryId, deliveryCountryId };
    },

    _extractEupagoDocumentInfo() {
        if (this.paymentContext.transactionRoute) {
            const isInvoice = this.paymentContext.transactionRoute.includes('/invoice/');
            const matches = this.paymentContext.transactionRoute.match(/\/transaction\/(\d+)/);
            const docId = matches?.[1] ? parseInt(matches[1]) : null;
            return { docId, isInvoice };
        }
        return { docId: null, isInvoice: false };
    },

    _calculateEupagoFees(baseAmount, provider, companyCountryId, deliveryCountryId) {
        const isInternational = deliveryCountryId && companyCountryId &&
                                deliveryCountryId !== companyCountryId;

        let totalFixedFees = 0;
        let totalPercentFees = 0;

        if (isInternational) {
            if (!provider.cr_eupago_is_free_international) {
                totalFixedFees = provider.cr_eupago_fix_international_fees || 0;
                totalPercentFees = (provider.cr_eupago_var_international_fees || 0) * baseAmount / 100;
            } else if (baseAmount < (provider.cr_eupago_free_international_amount || 0)) {
                totalFixedFees = provider.cr_eupago_fix_international_fees || 0;
                totalPercentFees = (provider.cr_eupago_var_international_fees || 0) * baseAmount / 100;
            }
        } else {
            if (!provider.cr_eupago_is_free_domestic) {
                totalFixedFees = provider.cr_eupago_fix_domestic_fees || 0;
                totalPercentFees = (provider.cr_eupago_var_domestic_fees || 0) * baseAmount / 100;
            } else if (baseAmount < (provider.cr_eupago_free_domestic_amount || 0)) {
                totalFixedFees = provider.cr_eupago_fix_domestic_fees || 0;
                totalPercentFees = (provider.cr_eupago_var_domestic_fees || 0) * baseAmount / 100;
            }
        }

        return Math.round((totalFixedFees + totalPercentFees) * 100) / 100;
    },

    _displayEupagoFeeBadge(radio, calculatedFees, providerData) {
        if (!radio) return;
        
        // Find the label or container associated with this radio button to append the badge
        // Odoo 16+ payment form structure: <div name="o_payment_option_card">...<label>...</label></div>
        const container = radio.closest('.o_payment_option_card') || radio.parentElement;
        if (!container) return;

        // Remove any existing badge to avoid duplicates
        const existingBadge = container.querySelector('.eupago-fees-badge');
        if (existingBadge) {
            existingBadge.remove();
        }

        const currencyId = parseInt(this.paymentContext.currencyId);

        rpc('/web/dataset/call_kw', {
            model: 'res.currency',
            method: 'read',
            args: [[currencyId], ['symbol']],
            kwargs: {},
            context: {},
        }).then(result => {
            const currencySymbol = result?.[0]?.symbol || '€';

            // Create badge
            const badge = document.createElement('span');
            badge.className = 'badge bg-primary ms-2 eupago-fees-badge';
            badge.style.fontSize = '12px';
            badge.style.padding = '3px 8px';
            badge.textContent = `+ ${currencySymbol}${calculatedFees.toFixed(2)} Fees`;

            // Append badge next to the payment option label
            const label = container.querySelector('label');
            if (label) {
                label.appendChild(badge);
            } else {
                container.appendChild(badge);
            }
        });
    }
});
