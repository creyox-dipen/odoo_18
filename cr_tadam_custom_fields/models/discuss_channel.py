# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import fields, models


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    x_tadam_ticket_id = fields.Char(string='x_tadam_ticket_id')
