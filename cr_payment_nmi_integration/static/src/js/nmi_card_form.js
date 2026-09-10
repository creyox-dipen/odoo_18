/** @odoo-module **/
// Part of Creyox Technologies

import PaymentForm from '@payment/js/payment_form';
import publicWidget from '@web/legacy/js/public/public_widget';
import { rpc } from '@web/core/network/rpc';

// ─── Extend PaymentForm (canonical Odoo 18 provider pattern) ─────────────────

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

// ─── BIN-Lookup fee display & Token Surcharge (publicWidget — Odoo 18 CE) ─────

publicWidget.registry.NmiCardFeeDisplay = publicWidget.Widget.extend({
    selector: '#o_payment_form',
    events: {
        'input #nmi_ccnumber': '_onCardInput',
        'change input[name="o_payment_radio"]': '_onRadioChange',
    },

    start() {
        this._super.apply(this, arguments);
        this._initTokenBadges();
        this._handleInitialSelection();
    },

    _initTokenBadges() {
        const badges = document.querySelectorAll('.nmi-token-fee-badge');
        if (!badges.length) return;

        const paymentForm = document.querySelector('#o_payment_form') || this.el;
        const baseAmount = parseFloat(paymentForm?.dataset.amount || 0);
        const currencyName = paymentForm?.dataset.currencyName || 'USD';

        badges.forEach((badge) => {
            const cardType = badge.dataset.cardType;
            const creditFee = parseFloat(badge.dataset.creditFee) || 0;
            const debitFee = parseFloat(badge.dataset.debitFee) || 0;

            let feePercent = 0;
            if (cardType === 'credit' || cardType === 'charge') {
                feePercent = creditFee;
            } else if (cardType === 'debit') {
                feePercent = debitFee;
            }

            if (feePercent > 0) {
                const feeAmount = (baseAmount * feePercent) / 100;
                const formatter = new Intl.NumberFormat('en-US', {
                    style: 'currency',
                    currency: currencyName,
                });
                badge.textContent = `+ ${formatter.format(feeAmount)} Fee`;
                badge.classList.remove('d-none');
            } else {
                badge.classList.add('d-none');
            }
        });
    },

    async _handleInitialSelection() {
        const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
        if (!checkedRadio) return;

        const ds = checkedRadio.dataset;
        const providerCode = ds.providerCode;
        const isToken = ds.paymentOptionType === 'token';

        if (isToken && providerCode === 'nmi') {
            const tokenId = ds.paymentOptionId;
            try {
                const result = await rpc('/payment/nmi/token_surcharge', {
                    token_id: parseInt(tokenId),
                });
                this._updateOrderSummaryDOM(result);
            } catch (error) {
                console.error('[NMI Token Surcharge] Initial RPC Error:', error);
            }
        }
    },

    async _onRadioChange(ev) {
        const target = ev ? ev.target : this.el.querySelector('input[name="o_payment_radio"]:checked');
        if (!target) return;

        const ds = target.dataset;
        const providerCode = ds.providerCode;
        const pmCode = ds.paymentMethodCode;
        const isToken = ds.paymentOptionType === 'token';

        if (isToken && providerCode === 'nmi') {
            const tokenId = ds.paymentOptionId;
            console.log('[NMI] Saved Token Selected:', tokenId);
            this.lastBin = null;
            this._updateFeeSummary(false);
            try {
                const result = await rpc('/payment/nmi/token_surcharge', {
                    token_id: parseInt(tokenId),
                });
                this._updateOrderSummaryDOM(result);
            } catch (error) {
                console.error('[NMI Token Surcharge] RPC Error:', error);
            }
        } else if (!isToken && providerCode === 'nmi' && pmCode !== 'ach_direct_debit') {
            const container = target.closest('[name="o_payment_option"]');
            const cardNumberInput = container?.querySelector('#nmi_ccnumber');
            const cardVal = cardNumberInput?.value?.replace(/\s+/g, '') || '';
            if (cardVal.length >= 6) {
                const bin = cardVal.substring(0, 6);
                this.lastBin = bin;
                const providerId = parseInt(ds.providerId);
                try {
                    const result = await rpc('/payment/nmi/bin_lookup', {
                        bin_number: bin,
                        provider_id: providerId,
                    });
                    this._updateFeeSummary(result.type);
                    this._updateOrderSummaryDOM(result);
                } catch (error) {
                    console.error('[NMI BIN Lookup] RPC Error:', error);
                }
            } else {
                this.lastBin = null;
                this._updateFeeSummary(false);
                await this._clearSurcharge();
            }
        } else {
            if (this.lastBin) {
                this.lastBin = null;
            }
            this._updateFeeSummary(false);
            await this._clearSurcharge();
        }
    },

    async _onCardInput(ev) {
        const cardNumber = ev.target.value.replace(/\s+/g, '');
        if (cardNumber.length < 6) {
            this.lastBin = null;
            this._updateFeeSummary(false);
            await this._clearSurcharge();
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
            this._updateOrderSummaryDOM(result);
        } catch (error) {
            console.error('[NMI BIN Lookup] Error:', error);
            this._updateFeeSummary(false);
        }
    },

    async _clearSurcharge() {
        try {
            const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
            const providerId = parseInt(checkedRadio?.dataset.providerId) || null;
            const result = await rpc('/payment/nmi/clear_surcharge', { provider_id: providerId });
            this._updateOrderSummaryDOM(result);
        } catch (error) {
            console.error('[NMI Clear Surcharge] RPC Error:', error);
        }
    },

    _updateOrderSummaryDOM(result) {
        if (!result) return;
        console.log('[NMI] Updating Order Summary DOM:', result);

        if (result.new_total !== undefined && result.new_total > 0) {
            const paymentForm = document.querySelector('#o_payment_form') || this.el;
            if (paymentForm) {
                paymentForm.dataset.amount = result.new_total;
            }
            document.querySelectorAll('[name="o_payment_submit_button"]').forEach((btn) => {
                btn.dataset.amount = result.new_total;
            });
        }

        const htmlToUse = result.total_html || result.summary_html;
        if (htmlToUse) {
            const cartTotals = document.querySelectorAll('#cart_total');
            if (cartTotals.length) {
                cartTotals.forEach((cartTotal) => {
                    const temp = document.createElement('div');
                    temp.innerHTML = htmlToUse;
                    const newTotal = temp.querySelector('#cart_total') || temp.firstElementChild;
                    if (newTotal && cartTotal.parentElement) {
                        cartTotal.replaceWith(newTotal);
                    }
                });
            }
        }

        if (result.cart_lines_html) {
            const cartProductsList = document.querySelectorAll('#cart_products');
            if (cartProductsList.length) {
                cartProductsList.forEach((cartProducts) => {
                    const temp = document.createElement('div');
                    temp.innerHTML = result.cart_lines_html;
                    const newProducts = temp.querySelector('#cart_products') || temp.firstElementChild;
                    if (newProducts && cartProducts.parentElement) {
                        cartProducts.replaceWith(newProducts);
                    }
                });
            }
        }

        const summaryTotalSpans = document.querySelectorAll('#amount_total_summary');
        if (summaryTotalSpans.length && result.new_total !== undefined) {
            const currencyName = this.el.dataset.currencyName || 'USD';
            const formatter = new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: currencyName,
            });
            summaryTotalSpans.forEach((span) => {
                span.textContent = formatter.format(result.new_total);
            });
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
