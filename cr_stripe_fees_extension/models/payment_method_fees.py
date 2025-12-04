# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api, _
import logging
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)

class PaymentMethodFees(models.Model):
    _name = "payment.method.fees"
    _description = "Fees Per Payment Method"

    payment_method_id = fields.Many2one("payment.method", string="Payment Method", required=True)
    default_method = fields.Boolean(string="Default Payment Method Fee")
    fix_domestic_fees = fields.Float(string="Fixed Domestic Fees")
    var_domestic_fees = fields.Float(string="Variable Domestic Fees (in percent)")
    is_free_domestic = fields.Boolean(string="Free Domestic Fees if Amount is Above")
    free_domestic_amount = fields.Float(string="Domestic Total Amount")
    fix_international_fees = fields.Float(string="Fixed International Fees")
    var_international_fees = fields.Float(string="Variable International Fees (in percent)")
    is_free_international = fields.Boolean(string="Free International Fees if Amount is Above")
    free_international_amount = fields.Float(string="International Total Amount")
    payment_provider_id = fields.Many2one(comodel_name="payment.provider")

    @api.constrains('default_method', 'payment_provider_id')
    def _check_unique_default_method(self):
        """
        Ensure only one record per payment_provider_id can have default_method=True.
        Triggered whenever default_method or payment_provider_id changes.
        """
        for record in self:
            if record.default_method and record.payment_provider_id:
                # Search for other defaults on the same provider (exclude self for updates)
                other_defaults = self.search_count([
                    ('payment_provider_id', '=', record.payment_provider_id.id),
                    ('default_method', '=', True),
                    ('id', '!=', record.id),
                ])
                if other_defaults > 0:
                    raise ValidationError(
                        _("Only one payment method can be set as default per payment provider!\n"
                          "Please unset the default on the existing line first.")
                    )

    @api.onchange('default_method')
    def _onchange_default_method(self):
        """
        Optional UI improvement: Warn or auto-adjust if needed, but constraint handles enforcement.
        """
        if self.default_method and self.payment_provider_id:
            # Check if another default exists (for preview in form)
            other_defaults = self.search([
                ('payment_provider_id', '=', self.payment_provider_id.id),
                ('default_method', '=', True),
                ('id', '!=', self.id),
            ], limit=1)
            if other_defaults:
                return {
                    'warning': {
                        'title': _("Warning"),
                        'message': _("Another payment method is already set as default for this provider. "
                                     "Saving this will replace it, but only one can be active."),
                    }
                }
