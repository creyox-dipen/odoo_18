# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    stripe_expense_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Stripe Expense Account",
        domain="[('account_type', '=', 'expense'), ('company_id', 'in', company_id)]",
        help="Default expense account for Stripe journal fees.",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        param = self.env["ir.config_parameter"].sudo().get_param
        account_id = param("account.stripe_expense_account_id", default=False)
        res.update(stripe_expense_account_id=int(account_id) if account_id else False)
        return res

    def set_values(self):
        super().set_values()
        self.env["ir.config_parameter"].sudo().set_param(
            "account.stripe_expense_account_id",
            (
                self.stripe_expense_account_id.id
                if self.stripe_expense_account_id
                else False
            ),
        )
        # Update the Stripe Fees product with the selected expense account
        product = (
            self.env["product.template"]
            .sudo()
            .search([("name", "=", "Stripe Fees")], limit=1)
        )
        if product and self.stripe_expense_account_id:
            product.write(
                {"property_account_expense_id": self.stripe_expense_account_id.id}
            )
