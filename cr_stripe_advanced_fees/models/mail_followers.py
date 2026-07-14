# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

import logging
import psycopg2
from odoo import models, api

_logger = logging.getLogger(__name__)


class MailFollowers(models.Model):
    _inherit = "mail.followers"

    @api.model_create_multi
    def create(self, vals_list):
        """Override to gracefully handle concurrent follower creation preventing unique constraint crashes."""
        try:
            with self.env.cr.savepoint():
                return super().create(vals_list)
        except psycopg2.errors.UniqueViolation:
            _logger.info(
                "Follower unique constraint violation occurred (already follows). Gracefully ignoring."
            )
            return self.env["mail.followers"]
        except Exception as e:
            if "mail_followers_res_partner_res_model_id_uniq" in str(e):
                _logger.info(
                    "Follower unique constraint violation occurred (already follows). Gracefully ignoring."
                )
                return self.env["mail.followers"]
            raise e
