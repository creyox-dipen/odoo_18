# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import fields, models

class Company(models.Model):
    _inherit = 'res.company'

    is_gelato = fields.Boolean("Gelato")
    api_key_for_gelato = fields.Char(string="API Key")
    webhook_secret_for_gelato = fields.Char(string="Webhook Secret")