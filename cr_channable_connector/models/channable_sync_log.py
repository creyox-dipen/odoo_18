# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields, api, _

class ChannableSyncLog(models.Model):
    _name = 'channable.sync.log'
    _description = 'Channable Sync Log'
    _order = 'start_datetime desc'

    name = fields.Char(string='Name', required=True)
    marketplace_id = fields.Many2one(
        'channable.marketplace', string='Marketplace', 
        required=True, ondelete='cascade'
    )
    start_datetime = fields.Datetime(string='Start Date & Time', required=True)
    end_datetime = fields.Datetime(string='End Date & Time', required=True)
    duration = fields.Float(string='Duration (seconds)', help='Duration in seconds')
    orders_count = fields.Integer(string='Total Orders Found')
    synced_count = fields.Integer(string='Orders Synced')
    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('partial', 'Partial')
    ], string='Status', required=True, default='success')
    notes = fields.Text(string='Notes / Errors')
