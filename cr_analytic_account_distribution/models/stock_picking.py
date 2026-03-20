# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields


class StockPicking(models.Model):
    _inherit = "stock.picking"

    analytic_account_manage = fields.Selection(
        selection=[
            ("move", "By Stock Move"),
            ("picking", "By Picking"),
            ("none", "Not Applicable"),
        ],
        string="Apply Analytic Accounting by : Picking or Move?",
    )
    analytic_mode = fields.Selection(
        selection=[
            ("analytic_account", "Analytic Account"),
            ("analytic_distribution", "Analytic Distribution"),
        ],
        compute="_compute_analytic_mode",
    )
    analytic_distribution = fields.Json(string="Analytic Distribution")
    analytic_precision = fields.Json(string="Analytic Precision")

    def _compute_analytic_mode(self):
        """Compute the analytic mode for the picking from the system config parameter.

        Reads the 'cr_analytic_account.analytic_account_setting' ir.config_parameter
        and assigns it to each record.
        """
        mode = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("cr_analytic_account.analytic_account_setting")
        )
        for rec in self:
            rec.analytic_mode = mode or False

    def action_detailed_operations(self):
        """Override to inject analytic_mode into the action context.

        The detailed operations list view uses column_invisible="context.get('analytic_mode')"
        to show/hide the analytic_account_id and analytic_distribution fields based on
        the system setting. The base action's context does not include analytic_mode,
        so we add it here — mirroring how Odoo injects 'picking_code' into the same context.
        """
        action = super().action_detailed_operations()
        analytic_mode = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("cr_analytic_account.analytic_account_setting")
        )
        action["context"]["analytic_mode"] = analytic_mode or False
        return action
