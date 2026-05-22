/** @odoo-module **/

import { Interaction } from '@web/public/interaction';
import { registry } from '@web/core/registry';
import { rpc, RPCError } from '@web/core/network/rpc';

export class NmiCardPaymentForm extends Interaction {
    static selector = '#o_payment_form';

    setup() {
        this._handlePayNowClick = this._onPayNowClick.bind(this);
        document.addEventListener('click', this._handlePayNowClick, true);
        
        // Listen for input on the card number field to detect card type and show fees
        this._handleCardInput = this._onCardInput.bind(this);
        this.el.addEventListener('input', this._handleCardInput);

        // Listen for radio button changes (selecting saved tokens)
        this._handleRadioChange = this._onRadioChange.bind(this);
        this.el.addEventListener('change', this._handleRadioChange);

        this.registerCleanup(() => {
            document.removeEventListener('click', this._handlePayNowClick, true);
            this.el.removeEventListener('input', this._handleCardInput);
            this.el.removeEventListener('change', this._handleRadioChange);
        });
    }

    _onRadioChange(ev) {
        if (ev.target.name !== 'o_payment_radio') return;
        
        const isToken = ev.target.dataset.paymentOptionType === 'token';
        // For now, we don't know the type of existing tokens on the client side 
        // unless we add it to the template. But we can hide the summary for now
        // or wait for a more advanced implementation.
        // Actually, let's just clear the summary when changing options.
        this._updateFeeSummary(false);
    }

    // =========================================================================
    // Card Type Detection & Fee Calculation
    // =========================================================================

    async _onCardInput(ev) {
        if (ev.target.id !== 'nmi_ccnumber') return;

        const cardNumber = ev.target.value.replace(/\s+/g, '');
        if (cardNumber.length < 6) {
            this.lastBin = null;
            this._updateFeeSummary(false);
            return;
        }

        const bin = cardNumber.substring(0, 6);
        if (this.lastBin === bin) return; 
        this.lastBin = bin;

        console.log('[NMI] Triggering BIN lookup for:', bin);

        try {
            const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
            const providerId = parseInt(checkedRadio?.dataset.providerId);
            
            console.log('[NMI] Sending RPC to Odoo with Provider ID:', providerId);

            const result = await rpc('/payment/nmi/bin_lookup', {
                bin_number: bin,
                provider_id: providerId,
            });

            console.log('[NMI] Lookup result from Odoo:', result);

            // NMI returns 'credit', 'debit', 'charge', or 'unknown'
            const isCredit = result.type === 'credit' || result.type === 'charge';
            console.log('[NMI] Decision - Is Credit/Charge?', isCredit);
            
            this._updateFeeSummary(result.type);
        } catch (error) {
            console.error('[NMI BIN Lookup] RPC Error:', error);
            this._updateFeeSummary(false);
        }
    }

    _updateFeeSummary(cardType) {
        const formContainer = this.el.classList.contains('o_payment_nmi_card_form') ? 
                             this.el : this.el.querySelector('.o_payment_nmi_card_form');
        const summary = this.el.querySelector('#nmi_fee_summary');
        if (!summary || !formContainer) return;

        const ctx = formContainer.dataset;
        const feeActive = ctx.feeActive === 'True' || ctx.feeActive === 'true' || ctx.feeActive === '1';
        
        // Map card type to the correct fee percentage
        let feePercent = 0;
        if (cardType === 'credit' || cardType === 'charge') {
            feePercent = parseFloat(ctx.creditFeePercent) || 0;
        } else if (cardType === 'debit') {
            feePercent = parseFloat(ctx.debitFeePercent) || 0;
        }

        if (feeActive && feePercent > 0) {
            const baseAmount = parseFloat(this.el.closest('.o_payment_form').dataset.amount) || 0;
            const fee = (baseAmount * feePercent) / 100;
            const total = baseAmount + fee;

            const formatter = new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: this.el.closest('.o_payment_form').dataset.currencyName || 'USD',
            });

            this.el.querySelector('#nmi_fee_amount').textContent = formatter.format(fee);
            this.el.querySelector('#nmi_total_amount').textContent = formatter.format(total);
            summary.classList.remove('d-none');
        } else {
            summary.classList.add('d-none');
        }
    }

    _formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount);
    }

    // =========================================================================
    // Event Interception
    // =========================================================================

    async _onPayNowClick(ev) {
        if (!ev.target.closest('[name="o_payment_submit_button"]')) return;

        const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
        if (!checkedRadio) return;

        const ds = checkedRadio.dataset;
        const providerCode = ds.providerCode;
        const pmCode = ds.paymentMethodCode;

        // Bail out immediately if this is not an NMI payment
        if (providerCode !== 'nmi') return;

        // Bail out for ACH direct debit (handled by the ACH form separately)
        if (pmCode === 'ach_direct_debit') return;

        // Bail out for saved tokens — check the container for card input fields
        // If no card number input exists in this option's container, it's a token
        const container = checkedRadio.closest('[name="o_payment_option"]');
        const cardNumberInput = container?.querySelector('#nmi_ccnumber');
        if (!cardNumberInput) return;  // Saved token — let Odoo handle it natively

        ev.stopImmediatePropagation();
        ev.preventDefault();

        await this._processCardPayment(checkedRadio);
    }

    async _processCardPayment(checkedRadio) {
        const optionContainer = checkedRadio.closest('[name="o_payment_option"]');
        const inlineForm = optionContainer?.querySelector('[name="o_payment_inline_form"]');

        const getValue = (id) => inlineForm?.querySelector(`#${id}`)?.value?.trim() ?? '';
        
        const ccnumber = getValue('nmi_ccnumber').replace(/\s+/g, '');
        const ccexp = getValue('nmi_ccexp');
        const cvv = getValue('nmi_cvv');

        if (!ccnumber || ccnumber.length < 13) {
            this._showError('Please enter a valid card number.');
            return;
        }
        if (!/^\d{2}\/\d{2}$/.test(ccexp)) {
            this._showError('Please enter expiry in MM/YY format.');
            return;
        }
        if (!/^\d{3,4}$/.test(cvv)) {
            this._showError('Please enter a valid CVV.');
            return;
        }

        this._setButtonState(true);

        try {
            const ctx = this.el.dataset;
            const transactionRoute = ctx.transactionRoute || '/shop/payment/transaction';

            // Check if the user wants to save their card
            const tokenizeCheckbox = optionContainer?.querySelector('input[name="o_payment_tokenize_checkbox"]');
            const tokenizationRequested = tokenizeCheckbox ? tokenizeCheckbox.checked : false;

            const transactionParams = {
                provider_id: parseInt(checkedRadio.dataset.providerId),
                payment_method_id: parseInt(checkedRadio.dataset.paymentOptionId),
                token_id: null,
                amount: ctx.amount !== undefined ? parseFloat(ctx.amount) : null,
                flow: 'direct',
                tokenization_requested: tokenizationRequested,
                landing_route: ctx.landingRoute || '/payment/status',
                access_token: ctx.accessToken || '',
                csrf_token: odoo.csrf_token,
            };

            const processingValues = await rpc(transactionRoute, transactionParams);

            if (!processingValues || processingValues.state === 'error') {
                this._showError('Payment initialisation failed: ' + (processingValues?.state_message || 'Unknown error'));
                return;
            }

            // Submit to our new card processing controller
            const form = document.createElement('form');
            form.method = 'post';
            form.action = '/payment/nmi/card/process';

            const formFields = {
                reference: processingValues.reference,
                ccnumber,
                ccexp,
                cvv,
                tokenize: tokenizationRequested ? '1' : '0',
            };

            for (const [name, value] of Object.entries(formFields)) {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = name;
                input.value = value;
                form.appendChild(input);
            }

            document.body.appendChild(form);
            form.submit();

        } catch (error) {
            console.error('[NMI Card] Error:', error);
            this._showError('An unexpected error occurred.');
        }
    }

    _setButtonState(disabled) {
        document.querySelectorAll('[name="o_payment_submit_button"]').forEach(btn => btn.disabled = disabled);
    }

    _showError(message) {
        this._setButtonState(false);
        window.alert(message);
    }
}

registry.category('public.interactions').add('payment.nmi_card_payment', NmiCardPaymentForm);
