# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields


class ChannableProject(models.Model):
    _name = 'channable.project'
    _description = 'Channable Project'

    name = fields.Char(string='Project Name', required=True)
    channable_identifier = fields.Char(
        string='Project Identifier', required=True,
        help='Identifier obtained from Channable'
    )
    connection_id = fields.Many2one(
        'channable.connection', string='Connection',
        required=True, ondelete='cascade'
    )
