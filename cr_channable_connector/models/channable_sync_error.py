# -*- coding: utf-8 -*-
# Part of Creyox Technologies
from odoo import models, fields, api, _


class ChannableSyncError(models.Model):
    _name = 'channable.sync.error'
    _description = 'Channable Sync Error'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'moment desc'

    name = fields.Char(string='Brief Description', required=True)
    reference = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('channable.sync.error') or 'New'
    )
    order_id = fields.Many2one('sale.order', string='Order', ondelete='set null')
    marketplace_id = fields.Many2one('channable.marketplace', string='Marketplace')

    action_attempted = fields.Selection([
        ('create_order', 'Create Order'),
        ('sync_order', 'Sync Order'),
        ('update_shipment', 'Update Shipment Info'),
        ('sync_state', 'Sync Order State'),
        ('sync_tracking', 'Sync Order Tracking Code'),
        ('confirm_order', 'Confirm Order'),
        ('cancel_order', 'Cancel Order'),
        ('push_stock', 'Push Product Stock'),
    ], string='Action Attempted', required=True)

    detailed_description = fields.Text(string='Detailed Description')
    moment = fields.Datetime(string='Moment', default=fields.Datetime.now, readonly=True)
    user_id = fields.Many2one(
        'res.users', string='Triggered By',
        default=lambda self: self.env.user, readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('reference') or vals['reference'] == 'New':
                vals['reference'] = (
                    self.env['ir.sequence'].next_by_code('channable.sync.error') or 'New'
                )
        errors = super().create(vals_list)
        for error in errors:
            if error.marketplace_id and error.marketplace_id.assign_error_user_id:
                selection_label = dict(
                    self._fields['action_attempted'].selection
                ).get(error.action_attempted, error.action_attempted)
                note = _('Error occurred during %s. Please review the details.', selection_label)
                if error.detailed_description:
                    note += f'<br/>Details: {error.detailed_description}'
                error.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=error.marketplace_id.assign_error_user_id.id,
                    summary=_('Channable Sync Error: %s', error.name),
                    note=note,
                )
        return errors
