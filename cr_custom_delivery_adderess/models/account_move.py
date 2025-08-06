# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = ['account.move']

    custom_state_id = fields.Many2one(comodel_name='res.country.state', string='State')
    custom_country_id = fields.Many2one(comodel_name='res.country', string='Country')
    custom_street = fields.Char(string='Street')
    custom_street2 = fields.Char(string='Street2')
    custom_zip = fields.Char(string='Zip')
    custom_city = fields.Char(string='City')
