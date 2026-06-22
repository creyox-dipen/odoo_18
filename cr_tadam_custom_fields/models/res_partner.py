# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_tadam_user_id = fields.Char(string='x_tadam_user_id')
    x_supplier_approved = fields.Boolean(string='x_supplier_approved')
    x_kyc_verified_at = fields.Datetime(string='x_kyc_verified_at')
    x_user_suspended = fields.Boolean(string='x_user_suspended')
    x_user_banned = fields.Boolean(string='x_user_banned')
