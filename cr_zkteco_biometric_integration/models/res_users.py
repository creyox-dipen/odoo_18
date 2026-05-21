# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    can_edit_biometric_data = fields.Boolean(
        string="Can Edit Biometric Data",
        help="If enabled, this user can edit, delete and fetch biometric data.",
        compute="_compute_can_edit_biometric_data",
        inverse="_inverse_can_edit_biometric_data",
        store=True,
    )

    @api.depends('groups_id')
    def _compute_can_edit_biometric_data(self):
        group = self.env.ref('cr_zkteco_biometric_integration.group_biometric_editor', raise_if_not_found=False)
        for user in self:
            if group:
                user.can_edit_biometric_data = group in user.groups_id
            else:
                user.can_edit_biometric_data = False

    def _inverse_can_edit_biometric_data(self):
        group = self.env.ref('cr_zkteco_biometric_integration.group_biometric_editor', raise_if_not_found=False)
        if not group:
            return
        for user in self:
            if user.can_edit_biometric_data:
                user.groups_id = [(4, group.id)]
            else:
                user.groups_id = [(3, group.id)]
