/** @odoo-module **/
// Part of Creyox Technologies

import { Interaction } from '@web/public/interaction';
import { registry } from '@web/core/registry';
import { rpc, RPCError } from '@web/core/network/rpc';

/**
 * NMI ACH Direct Debit — frontend payment handler.
 *
 * Problem this solves
 * -------------------
 * Odoo's base PaymentForm JS defaults every provider to the 'redirect' flow.
 * ACH is an *inline* (direct) flow — the bank fields are collected on-page
 * and submitted to our own server-side controller (/payment/nmi/ach/process),
 * which then calls the NMI Direct Post API.  We cannot rely on the redirect
 * form mechanism for this.
 *
 * How it works
 * ------------
 * 1.  A document-level CAPTURE-phase listener intercepts every click on the
 *     "Pay Now" button before Odoo's base PaymentForm bubble-phase handler fires.
 * 2.  If the selected option is NOT NMI ACH, we return immediately — the event
 *     propagates normally and Odoo's base PaymentForm handles everything else
 *     (including the NMI card/Ekashu redirect flow).
 * 3.  If it IS NMI ACH we call stopImmediatePropagation() to prevent the base
 *     PaymentForm from also processing the click, then run our own flow:
 *       a.  Validate the inline form fields client-side.
 *       b.  Create the Odoo payment transaction via the standard transaction RPC
 *           (same route Odoo's JS would use) — this gives us the transaction
 *           reference, amount, and ach_process_url from processingValues.
 *       c.  Build a hidden <form> and submit it to /payment/nmi/ach/process so
 *           the bank details travel browser → Odoo (HTTPS) → NMI, never to an
 *           external page.
 *
 * Card (Ekashu redirect) flow
 * ---------------------------
 * Completely unaffected.  The guard `providerCode !== 'nmi' || pmCode !== 'ach_direct_debit'`
 * means every other payment option (including NMI card) falls through to
 * Odoo's base PaymentForm without modification.
 *
 * ACH form visibility fix
 * -----------------------
 * Odoo's `inline_form_view_id` is set at the *provider* level, so the ACH
 * form HTML is server-rendered into the inline-form div of EVERY NMI payment
 * option (card, credit, ACH).  On page load, `_hideAchFormForNonAchOptions()`
 * empties those divs for non-ACH options so the bank fields are never visible
 * when the user selects Card or Credit.
 */
export class NmiAchPaymentForm extends Interaction {
    static selector = '#o_payment_form';

    // =========================================================================
    // Interaction lifecycle
    // =========================================================================

    setup() {
        // Bind a CAPTURE-phase listener at document level.
        // Capture fires before the target-element bubble-phase listener that
        // Odoo's base PaymentForm registers via dynamicContent.
        // stopImmediatePropagation() in capture prevents ALL subsequent
        // handlers (including bubble-phase ones on the button itself).
        this._handlePayNowClick = this._onPayNowClick.bind(this);
        document.addEventListener('click', this._handlePayNowClick, true);
        this.registerCleanup(() => {
            document.removeEventListener('click', this._handlePayNowClick, true);
        });
    }

    // =========================================================================
    // Event interception
    // =========================================================================

    /**
     * Intercept Pay Now clicks.
     *
     * Forwards control to our ACH handler only when:
     *   - the clicked element is (or is inside) the payment submit button, AND
     *   - the selected radio has provider_code = 'nmi', AND
     *   - the selected radio has payment_method_code = 'ach_direct_debit'.
     *
     * Every other combination is allowed to propagate normally.
     *
     * @param {MouseEvent} ev
     */
    async _onPayNowClick(ev) {
        // Only care about the payment submit button.
        if (!ev.target.closest('[name="o_payment_submit_button"]')) {
            return;
        }

        // Find the selected payment radio button.
        const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
        if (!checkedRadio) {
            return;
        }

        const providerCode = checkedRadio.dataset.providerCode;
        const pmCode = checkedRadio.dataset.paymentMethodCode;

        // Guard: handle ONLY NMI ACH Direct Debit.
        // The NMI card (Ekashu redirect) flow has pmCode = 'card'/'credit', so
        // it falls through here and Odoo's base PaymentForm handles it normally.
        if (providerCode !== 'nmi' || pmCode !== 'ach_direct_debit') {
            return;
        }

        // Intercept: stop Odoo's base PaymentForm from also handling this click.
        ev.stopImmediatePropagation();
        ev.preventDefault();

        await this._processAchPayment(checkedRadio);
    }

    // =========================================================================
    // ACH payment flow
    // =========================================================================

    /**
     * Run the full ACH payment sequence for NMI Direct Debit.
     *
     * @param {HTMLInputElement} checkedRadio  The selected payment option radio.
     */
    async _processAchPayment(checkedRadio) {
        // ── Step 1: Locate and read the inline form fields ────────────────────
        const optionContainer = checkedRadio.closest('[name="o_payment_option"]');
        const inlineForm = optionContainer?.querySelector('[name="o_payment_inline_form"]');

        if (!inlineForm) {
            this._showError('ACH payment form not found. Please refresh the page and try again.');
            return;
        }

        /**
         * Helper: read and trim a named field's value from the inline form.
         * @param {string} name  The input's name attribute.
         * @returns {string}
         */
        const getValue = (name) =>
            inlineForm.querySelector(`[name="${name}"]`)?.value?.trim() ?? '';

        const checkname         = getValue('checkname');
        const checkaba          = getValue('checkaba');
        const checkaccount      = getValue('checkaccount');
        const account_type      = getValue('account_type')        || 'checking';
        const account_holder_type = getValue('account_holder_type') || 'personal';

        // ── Step 2: Client-side validation ───────────────────────────────────
        if (!checkname) {
            this._showError('Please enter the Account Holder Name.');
            return;
        }
        if (!/^\d{9}$/.test(checkaba)) {
            this._showError('Routing number must be exactly 9 digits.');
            return;
        }
        if (!checkaccount) {
            this._showError('Please enter the Account Number.');
            return;
        }

        // ── Step 3: Disable UI while processing ───────────────────────────────
        this._setButtonState(true);

        try {
            // ── Step 4: Create Odoo payment transaction via standard RPC ──────
            // This mirrors what Odoo's base PaymentForm does via
            // _initiatePaymentFlow → RPC(transactionRoute, params).
            // The server calls _get_specific_rendering_values() which — for
            // ACH — returns: reference, amount, partner_name, ach_process_url.
            const ctx = this.el.dataset;
            const transactionRoute = ctx.transactionRoute || '/shop/payment/transaction';

            const tokenizeCheckbox = optionContainer?.querySelector('input[name="o_payment_tokenize_checkbox"]');
            const tokenization_requested = tokenizeCheckbox ? tokenizeCheckbox.checked : false;

            const transactionParams = {
                provider_id:             parseInt(checkedRadio.dataset.providerId),
                payment_method_id:       parseInt(checkedRadio.dataset.paymentOptionId),
                token_id:                null,
                amount:                  ctx.amount !== undefined ? parseFloat(ctx.amount) : null,
                flow:                    'direct',
                tokenization_requested,
                landing_route:           ctx.landingRoute || '/payment/status',
                is_validation:           false,
                access_token:            ctx.accessToken || '',
                csrf_token:              odoo.csrf_token,
            };

            const processingValues = await rpc(transactionRoute, transactionParams);

            // Check for server-side errors returned in the payload.
            if (!processingValues || processingValues.state === 'error') {
                const msg = processingValues?.state_message || 'Unknown error.';
                this._showError('Payment initialisation failed: ' + msg);
                this._setButtonState(false);
                return;
            }

            // ── Step 5: Submit ACH fields to the NMI controller ───────────────
            // We build a hidden <form> and submit it programmatically so that:
            //   • bank details travel over HTTPS (browser → Odoo → NMI),
            //   • the URL is our own controller, not an external page.
            const achUrl = processingValues.ach_process_url || '/payment/nmi/ach/process';

            const form = document.createElement('form');
            form.method = 'post';
            form.action = achUrl;

            // Fields required by the NMI ACH controller.
            const formFields = {
                reference:            processingValues.reference    || '',
                amount:               processingValues.amount       || '',
                checkname,
                checkaba,
                checkaccount,
                account_type,
                account_holder_type,
                tokenize:             tokenization_requested,
            };

            for (const [name, value] of Object.entries(formFields)) {
                const input = document.createElement('input');
                input.type  = 'hidden';
                input.name  = name;
                input.value = value;
                form.appendChild(input);
            }

            // Append to body and submit — the NMI controller handles the rest
            // and redirects to /payment/status.
            document.body.appendChild(form);
            form.submit();

        } catch (error) {
            if (error instanceof RPCError) {
                this._showError('Payment processing failed: ' + error.data.message);
            } else {
                console.error('[NMI ACH] Unexpected error during payment:', error);
                this._showError('An unexpected error occurred. Please refresh the page and try again.');
            }
            this._setButtonState(false);
        }
    }

    // =========================================================================
    // UI helpers
    // =========================================================================

    /**
     * Enable or disable every Pay Now submit button on the page.
     *
     * @param {boolean} disabled  True to disable (processing), false to re-enable.
     */
    _setButtonState(disabled) {
        document.querySelectorAll('[name="o_payment_submit_button"]').forEach((btn) => {
            btn.disabled = disabled;
        });
    }

    /**
     * Display an error message.  Re-enables the button so the user can retry.
     *
     * @param {string} message
     */
    _showError(message) {
        this._setButtonState(false);
        // Use Odoo's dialog if available, otherwise fall back to window.alert.
        window.alert(message);
    }
}

registry.category('public.interactions').add('payment.nmi_ach_payment', NmiAchPaymentForm);
