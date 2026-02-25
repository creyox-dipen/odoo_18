# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields

class DataProcessingLog(models.Model):
    _name = 'cr.data.processing.log'
    _description = 'Log of data processing operations'

    cr_configuration_id = fields.Many2one('chargebee.configuration', string='Chargebee Config', required=True)
    cr_table_name = fields.Char('Name', required=True)
    cr_record_count = fields.Integer('Number of Records', required=True)
    cr_status = fields.Selection([
        ('success', 'Success'),
        ('failure', 'Failure')
    ], default='success', required=True)
    cr_error_message = fields.Text('Error Message')
    cr_timestamp = fields.Char('Timestamp')
    cr_initiated_at = fields.Char('Created At')
    cr_message = fields.Char('Message')
    cr_context = fields.Selection([
        ('currencies', 'Currencies'),
        ('items', 'Items'),
        ('itemsfamily', 'Item Family'),
        ('customers', 'Customers'),
        ('taxes', 'Taxes'),
        ('invoices', 'Invoices'),
    ], string='Context', required=True, help="Identifies the context or page the log is related to.")

    def _log_data_processing(self, table_name, record_count, status, timespan, initiated_at, cr_configuration_id, context, error_message=''):
        """Logs data processing operations into the DataProcessingLog model."""
        self.env['cr.data.processing.log'].sudo().create({
            'cr_table_name': table_name,
            'cr_record_count': record_count,
            'cr_status': status,
            'cr_error_message': error_message,
            'cr_timestamp': timespan,
            'cr_initiated_at': initiated_at,
            'cr_configuration_id': cr_configuration_id,  # Ensure configuration is passed
            'cr_context': context,  # Include context
        })


