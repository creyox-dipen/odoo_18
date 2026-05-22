/** @odoo-module **/
// Part of Creyox Technologies

/**
 * NMI ACH Direct Debit — Odoo 18 CE frontend handler.
 *
 * WHY THIS APPROACH
 * ─────────────────
 * The original code used `Interaction` from `@web/public/interaction`, which is
 * an Odoo 19/SaaS feature NOT available in Odoo 18 CE. This caused the module
 * to fail loading entirely.
 *
 * The correct Odoo 18 CE pattern is PaymentForm.include() — same as payment_demo,
 * payment_stripe, payment_authorize, etc.
 *
 * HOW IT WORKS
 * ────────────
 * 1. _prepareInlineForm  → sets flow='direct' for NMI ACH so _initiatePaymentFlow
 *    calls _processDirectFlow instead of _processRedirectFlow.
 *
 * 2. _processDirectFlow  → handles ACH: reads bank fields, creates the Odoo
 *    transaction via the base RPC (_prepareTransactionRouteParams already sets
 *    flow='direct'), then POSTs to /payment/nmi/ach/process.
 *    Note: the base _initiatePaymentFlow makes the transaction RPC and passes
 *    processingValues here — no need to make a separate RPC call.
 *
 * 3. _processRedirectFlow → safety net for ACH in case flow is still 'redirect'.
 *
 * ACH FORM VISIBILITY
 * ───────────────────
 * Odoo sets inline_form_view_id at the provider level, so the same inline form
 * HTML is rendered for ALL NMI payment methods (card, credit, ACH).
 * The server-rendered template must handle showing/hiding fields based on the
 * payment method. The _prepareInlineForm override handles the flow selection.
 */

import PaymentForm from '@payment/js/payment_form';
import { rpc, RPCError } from '@web/core/network/rpc';

// ─── Extend PaymentForm for NMI ACH ──────────────────────────────────────────

PaymentForm.include({

    /**
     * Override _prepareInlineForm to set flow='direct' for NMI ACH.
     *
     * @override method from @payment/js/payment_form
     */
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode === 'nmi' && paymentMethodCode === 'ach_direct_debit' && flow !== 'token') {
            this._setPaymentFlow('direct');
        }
        return this._super(...arguments);
    },

    /**
     * Override _processDirectFlow to handle NMI ACH payment.
     * Called when paymentContext.flow === 'direct'.
     * processingValues is already provided by the base _initiatePaymentFlow RPC.
     *
     * @override method from @payment/js/payment_form
     */
    async _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'nmi' || paymentMethodCode !== 'ach_direct_debit') {
            this._super(...arguments);
            return;
        }
        await this._submitNmiAchForm(processingValues);
    },

    /**
     * Override _processRedirectFlow — safety net for NMI ACH.
     * If flow is still 'redirect', catch here before crash.
     *
     * @override method from @payment/js/payment_form
     */
    async _processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'nmi' || paymentMethodCode !== 'ach_direct_debit') {
            this._super(...arguments);
            return;
        }
        await this._submitNmiAchForm(processingValues);
    },

    /**
     * Read ACH fields, validate, and POST to /payment/nmi/ach/process.
     * processingValues.reference is provided by the base _initiatePaymentFlow RPC.
     *
     * @param {object} processingValues  Transaction processing values from server.
     */
    async _submitNmiAchForm(processingValues) {
        // Locate the inline ACH form fields.
        const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
        const optionContainer = checkedRadio?.closest('[name="o_payment_option"]');
        const inlineForm = optionContainer?.querySelector('[name="o_payment_inline_form"]')
            || this.el; // fallback: search entire form

        const getValue = (name) =>
            (inlineForm.querySelector(`[name="${name}"]`) || this.el.querySelector(`[name="${name}"]`))
                ?.value?.trim() ?? '';

        const checkname           = getValue('checkname');
        const checkaba            = getValue('checkaba');
        const checkaccount        = getValue('checkaccount');
        const account_type        = getValue('account_type') || 'checking';
        const account_holder_type = getValue('account_holder_type') || 'personal';

        // ── Client-side validation ─────────────────────────────────────────────
        if (!checkname) {
            this._enableButton();
            window.alert('Please enter the Account Holder Name.');
            return;
        }
        if (!/^\d{9}$/.test(checkaba)) {
            this._enableButton();
            window.alert('Routing number must be exactly 9 digits.');
            return;
        }
        if (!checkaccount) {
            this._enableButton();
            window.alert('Please enter the Account Number.');
            return;
        }

        // ── Build hidden form and POST to Odoo ACH controller ─────────────────
        // Bank details travel: browser → Odoo (HTTPS) → NMI (server-to-server).
        const achUrl = processingValues.ach_process_url || '/payment/nmi/ach/process';

        const form = document.createElement('form');
        form.method = 'post';
        form.action = achUrl;

        const formFields = {
            reference:            processingValues.reference || '',
            amount:               processingValues.amount    || '',
            checkname,
            checkaba,
            checkaccount,
            account_type,
            account_holder_type,
            tokenize: this.paymentContext['tokenizationRequested'] ? '1' : '0',
        };

        for (const [name, value] of Object.entries(formFields)) {
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
