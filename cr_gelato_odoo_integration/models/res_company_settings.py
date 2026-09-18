# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    is_gelato = fields.Boolean(related='company_id.is_gelato',string="Gelato",readonly=False)
    api_key_for_gelato = fields.Char(related='company_id.api_key_for_gelato',string="API Key",readonly=False)
    webhook_secret_for_gelato = fields.Char(related='company_id.webhook_secret_for_gelato',string="Webhook Secret",readonly=False)