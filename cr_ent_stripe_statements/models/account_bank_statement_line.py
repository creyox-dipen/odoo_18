# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import _, models, fields, api
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger(__name__)
from odoo.exceptions import UserError


class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement.line"

    @api.depends("move_id.line_ids.reconciled", "move_id.line_ids.account_id.reconcile")
    def _compute_is_reconciled(self):
        super()._compute_is_reconciled()
        for line in self:
            # Custom logic: Force unreconciled for refund lines (identify via payment_ref containing 'Refund for')
            if "Refund for" in (line.payment_ref or ""):
                line.is_reconciled = False

            if "Stripe Fee for" in (line.payment_ref or ""):
                line.is_reconciled = False

    def _cron_try_auto_reconcile_statement_lines(self, batch_size=None, limit_time=0):
        # Call super to keep original logic, but modify domain to skip STRP journal
        logger.info("cron overrided")

        def _compute_st_lines_to_reconcile(configured_company):
            remaining_line_id = None
            limit = batch_size + 1 if batch_size else None
            domain = [
                ("is_reconciled", "=", False),
                ("create_date", ">", start_time.date() - relativedelta(months=3)),
                ("company_id", "in", configured_company.ids),
                ("journal_id.code", "!=", "STRP"),  # Skip Stripe journal
            ]
            st_lines = self.search(
                domain, limit=limit, order="cron_last_check ASC NULLS FIRST, id"
            )
            if batch_size and len(st_lines) > batch_size:
                remaining_line_id = st_lines[batch_size].id
                st_lines = st_lines[:batch_size]
            return st_lines, remaining_line_id

        start_time = fields.Datetime.now()

        # Original company check
        configured_company = children_company = (
            self.env["account.reconcile.model"]
            .search_fetch(
                [
                    ("auto_reconcile", "=", True),
                    ("rule_type", "in", ("writeoff_suggestion", "invoice_matching")),
                ],
                ["company_id"],
            )
            .company_id
        )
        if not configured_company:
            return
        while children_company := children_company.child_ids:
            configured_company += children_company

        st_lines, remaining_line_id = (
            (self, None) if self else _compute_st_lines_to_reconcile(configured_company)
        )

        if not st_lines:
            return

        # Original lock and reconciliation loop (unchanged)
        self.env.cr.execute(
            "SELECT 1 FROM account_bank_statement_line WHERE id in %s FOR UPDATE",
            [tuple(st_lines.ids)],
        )

        nb_auto_reconciled_lines = 0
        for index, st_line in enumerate(st_lines):
            if (
                limit_time
                and fields.Datetime.now().timestamp() - start_time.timestamp()
                > limit_time
            ):
                remaining_line_id = st_line.id
                st_lines = st_lines[:index]
                break
            wizard = (
                self.env["bank.rec.widget"]
                .with_context(default_st_line_id=st_line.id)
                .new({})
            )
            wizard._action_trigger_matching_rules()
            if wizard.state == "valid" and wizard.matching_rules_allow_auto_reconcile:
                try:
                    wizard._action_validate()
                    if st_line.is_reconciled:
                        st_line.move_id.message_post(
                            body=_(
                                "This bank transaction has been automatically validated using the reconciliation model '%s'.",
                                ", ".join(
                                    st_line.move_id.line_ids.reconcile_model_id.mapped(
                                        "name"
                                    )
                                ),
                            )
                        )
                        nb_auto_reconciled_lines += 1
                except UserError as e:
                    logger.info(
                        "Failed to auto reconcile statement line %s due to user error: %s",
                        st_line.id,
                        str(e),
                    )
                    continue

        st_lines.write({"cron_last_check": start_time})

        if remaining_line_id:
            remaining_st_line = self.env["account.bank.statement.line"].browse(
                remaining_line_id
            )
            if nb_auto_reconciled_lines or not remaining_st_line.cron_last_check:
                self.env.ref(
                    "account_accountant.auto_reconcile_bank_statement_line"
                )._trigger()
