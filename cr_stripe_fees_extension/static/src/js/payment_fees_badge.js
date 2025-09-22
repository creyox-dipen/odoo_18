///** @odoo-module */
//import paymentForm from '@payment/js/payment_form';
//
//paymentForm.include({
//    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
//        // Call original method first
//        await this._super(...arguments);
//
//        if (providerCode !== 'stripe') return;
//
//        const radio = document.querySelector('input[name="o_payment_radio"]:checked');
//        const inlineForm = this._getInlineForm(radio);
//        const stripeInlineForm = inlineForm.querySelector('[name="o_stripe_element_container"]');
//
//        // Read fees from inline_form_values
//        const fees = this.stripeInlineFormValues['fees'] || 0;
//        const currencySign = this.stripeInlineFormValues['currency_symbol'] || '';
//
//        if (fees > 0) {
//            // Avoid duplicate badge
//            if (!stripeInlineForm.querySelector('.o_stripe_fees_badge')) {
//                const badge = document.createElement('span');
//                badge.className = 'o_stripe_fees_badge badge bg-info text-dark ms-2';
//                badge.style.fontSize = '0.9em';
//                badge.innerText = `+ ${currencySign}${fees.toFixed(2)} Fees`;
//
//                // Append inside the Stripe element container (after card options)
//                stripeInlineForm.appendChild(badge);
//            }
//        }
//    },
//});

/** @odoo-module */
import paymentForm from '@payment/js/payment_form';

paymentForm.include({
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        // call original first (this mounts Stripe element)
        await this._super(...arguments);

        if (providerCode !== 'stripe') return;
        if (!this.stripeInlineFormValues) return;

        // read fees + symbol passed from backend
        const fees = Number(this.stripeInlineFormValues['fees'] || 0);
        const currencySign = this.stripeInlineFormValues['currency_symbol'] || '';

        // helper to create badge element
        const createBadge = (f, cur) => {
            const span = document.createElement('span');
            span.className = 'o_stripe_fees_badge_inline';
            span.setAttribute('aria-hidden', 'true');
            span.textContent = `+ ${cur}${Number(f).toFixed(2)} Fees`;
            return span;
        };

        // find stripe inline container (same as earlier working code)
        const radio = document.querySelector('input[name="o_payment_radio"]:checked');
        if (!radio) return;
        const inlineForm = this._getInlineForm(radio);
        if (!inlineForm) return;
        const stripeInlineForm = inlineForm.querySelector('[name="o_stripe_element_container"]') || inlineForm;
        if (!stripeInlineForm) return;

        // remove existing badges to avoid duplicates
        const removeBadges = (root) => {
            const existing = root.querySelectorAll('.o_stripe_fees_badge_inline');
            existing.forEach(n => n.remove());
        };
        removeBadges(stripeInlineForm);

        if (!(fees > 0)) return; // nothing to show

        // Try to find the selected payment-method row inside stripeInlineForm
        let selectedItem = stripeInlineForm.querySelector('.p-PickerItem--selected, .PickerItem--selected');
        // fallback to global search if not found inside (some stripe versions render slightly differently)
        if (!selectedItem) {
            selectedItem = document.querySelector('.p-PickerItem--selected, .PickerItem--selected');
        }
        // If still not found, fallback to the first picker item (graceful)
        if (!selectedItem) {
            selectedItem = stripeInlineForm.querySelector('.p-PickerItem, .PickerItem, .p-PickerItem') || null;
        }
        if (!selectedItem) {
            // As last resort, append below provider container (this was your previous working state)
            const badge = createBadge(fees, currencySign);
            stripeInlineForm.appendChild(badge);
            return;
        }

        // Find the title element inside the selected item (where "Visa Credit" is)
        const titleEl = selectedItem.querySelector('.p-PickerItem-title, .PickerItem-title, h3');
        if (!titleEl) {
            // if no title found, append to selectedItem container
            const fallbackBadge = createBadge(fees, currencySign);
            selectedItem.appendChild(fallbackBadge);
            return;
        }

        // Insert badge inline with title: place it after the title element's parent
        // Many Stripe DOMs have title inside a container; appending to that parent keeps layout consistent.
        const parentForBadge = titleEl.parentElement || titleEl;
        // remove if any left from earlier
        const existingHere = parentForBadge.querySelector('.o_stripe_fees_badge_inline');
        if (existingHere) existingHere.remove();

        const badgeNode = createBadge(fees, currencySign);
        // Prefer insertAfter behavior:
        if (titleEl.nextSibling) {
            titleEl.parentElement.insertBefore(badgeNode, titleEl.nextSibling);
        } else {
            parentForBadge.appendChild(badgeNode);
        }

        // Observe stripeInlineForm for re-renders and re-attach badge (debounced)
        if (!stripeInlineForm.__paymentFeesObserver) {
            let t = null;
            const obs = new MutationObserver(() => {
                clearTimeout(t);
                t = setTimeout(() => {
                    try {
                        removeBadges(stripeInlineForm);
                        // Re-run insertion logic (same as above)
                        let sel = stripeInlineForm.querySelector('.p-PickerItem--selected, .PickerItem--selected') ||
                                  document.querySelector('.p-PickerItem--selected, .PickerItem--selected') ||
                                  stripeInlineForm.querySelector('.p-PickerItem, .PickerItem, .p-PickerItem');
                        if (sel) {
                            const tEl = sel.querySelector('.p-PickerItem-title, .PickerItem-title, h3');
                            const parent = (tEl && tEl.parentElement) || sel;
                            if (parent) {
                                // remove any left duplicates then insert
                                const existing = parent.querySelector('.o_stripe_fees_badge_inline');
                                if (existing) existing.remove();
                                const newBadge = createBadge(fees, currencySign);
                                if (tEl && tEl.nextSibling) {
                                    tEl.parentElement.insertBefore(newBadge, tEl.nextSibling);
                                } else {
                                    parent.appendChild(newBadge);
                                }
                            }
                        }
                    } catch (e) {
                        // silent
                        // console.warn('payment fees reattach error', e)
                    }
                }, 120);
            });
            obs.observe(stripeInlineForm, { childList: true, subtree: true, attributes: true });
            stripeInlineForm.__paymentFeesObserver = obs;
        }
    },
});
