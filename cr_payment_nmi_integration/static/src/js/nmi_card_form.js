/** @odoo-module **/
// Part of Creyox Technologies

/**
 * NMI Card Payment — Odoo 18 CE frontend handler.
 *
 * WHY THIS APPROACH
 * ─────────────────
 * The original code used `Interaction` from `@web/public/interaction`, which is
 * an Odoo 19/SaaS feature NOT available in Odoo 18 CE. This caused the module
 * to fail loading entirely with:
 *   "@web/public/interaction not in correct asset bundle"
 *
 * The correct Odoo 18 CE pattern (used by payment_demo, payment_stripe, etc.) is
 * to import PaymentForm from '@payment/js/payment_form' and use .include() to
 * extend it with provider-specific overrides.
 *
 * HOW IT WORKS
 * ────────────
 * 1. _prepareInlineForm  → sets paymentContext.flow = 'direct' for NMI card.
 *    This makes _getPaymentFlow() return 'direct' at submit time so
 *    _initiatePaymentFlow calls _processDirectFlow (safe no-op) instead of
 *    _processRedirectFlow (which crashes when redirect_form_html is missing).
 *
 * 2. _processDirectFlow  → handles NMI card via POST to /payment/nmi/card/process.
 *    processingValues.reference is already created by the base RPC call.
 *    paymentContext.tokenizationRequested is already set by _submitForm.
 *
 * 3. _processRedirectFlow → CRITICAL SAFETY NET. If flow is still 'redirect'
 *    (edge case: radio pre-selected and _expandInlineForm not yet called),
 *    we intercept here before the null.setAttribute crash.
 *
 * 4. NmiCardFeeDisplay publicWidget → BIN-lookup fee display using the
 *    standard Odoo 18 publicWidget pattern (no Interaction needed).
 */

import PaymentForm from '@payment/js/payment_form';
import publicWidget from '@web/legacy/js/public/public_widget';
import { rpc } from '@web/core/network/rpc';

// ─── Extend PaymentForm (canonical Odoo 18 provider pattern) ─────────────────
// Same pattern as payment_demo, payment_stripe, payment_authorize, etc.

PaymentForm.include({

    /**
     * Override _prepareInlineForm to set flow='direct' for NMI card.
     *
     * @override method from @payment/js/payment_form
     */
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode === 'nmi' && paymentMethodCode !== 'ach_direct_debit' && flow !== 'token') {
            this._setPaymentFlow('direct');
        }
        return this._super(...arguments);
    },

    /**
     * Override _processDirectFlow to handle NMI card payment.
     * Called when paymentContext.flow === 'direct' (set by _prepareInlineForm above).
     *
     * @override method from @payment/js/payment_form
     */
    async _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'nmi' || paymentMethodCode === 'ach_direct_debit') {
            this._super(...arguments);
            return;
        }
        const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
        if (!checkedRadio || this._getPaymentOptionType(checkedRadio) === 'token') {
            this._super(...arguments);
            return;
        }
        this._submitNmiCardForm(processingValues);
    },

    /**
     * Override _processRedirectFlow — CRITICAL SAFETY NET.
     * If flow is still 'redirect', intercept here before the null.setAttribute crash.
     * processingValues.reference is already available from the base RPC.
     *
     * @override method from @payment/js/payment_form
     */
    _processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'nmi' || paymentMethodCode === 'ach_direct_debit') {
            this._super(...arguments);
            return;
        }
        const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
        if (!checkedRadio || this._getPaymentOptionType(checkedRadio) === 'token') {
            this._super(...arguments);
            return;
        }
        // Intercept NMI card redirect — prevents null.setAttribute crash.
        this._submitNmiCardForm(processingValues);
    },

    /**
     * Shared helper: validate card fields and POST to /payment/nmi/card/process.
     * Card data travels: browser → Odoo HTTPS → NMI API (server-to-server).
     */
    _submitNmiCardForm(processingValues) {
        // Read card fields from the payment form (works even if inline form is d-none).
        const getValue = (id) => this.el.querySelector(`#${id}`)?.value?.trim() ?? '';

        const ccnumber = getValue('nmi_ccnumber').replace(/\s+/g, '');
        const ccexp    = getValue('nmi_ccexp');
        const cvv      = getValue('nmi_cvv');

        if (!ccnumber || ccnumber.length < 13) {
            this._enableButton();
            window.alert('Please enter a valid card number.');
            return;
        }
        if (!/^\d{2}\/\d{2}$/.test(ccexp)) {
            this._enableButton();
            window.alert('Please enter the expiry date in MM/YY format.');
            return;
        }
        if (!/^\d{3,4}$/.test(cvv)) {
            this._enableButton();
            window.alert('Please enter a valid CVV (3 or 4 digits).');
            return;
        }

        // paymentContext.tokenizationRequested is set by _submitForm (line 154-156).
        const form = document.createElement('form');
        form.method = 'post';
        form.action = '/payment/nmi/card/process';

        const fields = {
            reference: processingValues.reference,
            ccnumber,
            ccexp,
            cvv,
            tokenize: this.paymentContext['tokenizationRequested'] ? '1' : '0',
        };

        for (const [name, value] of Object.entries(fields)) {
            const input = document.createElement('input');
            input.type  = 'hidden';
            input.name  = name;
            input.value = value;
            form.appendChild(input);
        }

        document.body.appendChild(form);
        form.submit();
    },
});

// ─── BIN-Lookup fee display (publicWidget — Odoo 18 CE compatible) ────────────

publicWidget.registry.NmiCardFeeDisplay = publicWidget.Widget.extend({
    selector: '#o_payment_form',
    events: {
        'input #nmi_ccnumber': '_onCardInput',
        'change input[name="o_payment_radio"]': '_onRadioChange',
    },

    _onRadioChange() {
        this._updateFeeSummary(false);
        this.lastBin = null;
    },

    async _onCardInput(ev) {
        const cardNumber = ev.target.value.replace(/\s+/g, '');
        if (cardNumber.length < 6) {
            this.lastBin = null;
            this._updateFeeSummary(false);
            return;
        }

        const bin = cardNumber.substring(0, 6);
        if (this.lastBin === bin) return;
        this.lastBin = bin;

        try {
            const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
            const providerId   = parseInt(checkedRadio?.dataset.providerId);
            const result = await rpc('/payment/nmi/bin_lookup', {
                bin_number:  bin,
                provider_id: providerId,
            });
            this._updateFeeSummary(result.type);
        } catch (error) {
            console.error('[NMI BIN Lookup] Error:', error);
            this._updateFeeSummary(false);
        }
    },

    _updateFeeSummary(cardType) {
        const formContainer = this.el.classList.contains('o_payment_nmi_card_form')
            ? this.el
            : this.el.querySelector('.o_payment_nmi_card_form');
        const summary = this.el.querySelector('#nmi_fee_summary');
        if (!summary || !formContainer) return;

        const ctx       = formContainer.dataset;
        const feeActive = ctx.feeActive === 'True' || ctx.feeActive === 'true' || ctx.feeActive === '1';

        let feePercent = 0;
        if (cardType === 'credit' || cardType === 'charge') {
            feePercent = parseFloat(ctx.creditFeePercent) || 0;
        } else if (cardType === 'debit') {
            feePercent = parseFloat(ctx.debitFeePercent) || 0;
        }

        if (feeActive && feePercent > 0) {
            const baseAmount   = parseFloat(this.el.dataset.amount) || 0;
            const fee          = (baseAmount * feePercent) / 100;
            const total        = baseAmount + fee;
            const currencyName = this.el.dataset.currencyName || 'USD';
            const formatter    = new Intl.NumberFormat('en-US', { style: 'currency', currency: currencyName });

            const feeEl   = this.el.querySelector('#nmi_fee_amount');
            const totalEl = this.el.querySelector('#nmi_total_amount');
            if (feeEl)   feeEl.textContent  = formatter.format(fee);
            if (totalEl) totalEl.textContent = formatter.format(total);
            summary.classList.remove('d-none');
        } else {
            summary.classList.add('d-none');
        }
    },
});
