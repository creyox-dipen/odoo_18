# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class VendorQuotation(models.Model):
    _name = 'vendor.quotation'
    _description = 'Vendor Quotation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'total_amount asc, delivery_days asc'

    name = fields.Char(string="Quotation Reference", required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    purchase_id = fields.Many2one('purchase.order', string="RFQ Reference", required=True, ondelete='cascade', tracking=True)
    vendor_id = fields.Many2one('res.partner', string="Vendor", required=True, domain="[('supplier_rank', '>', 0)]", tracking=True)
    submission_date = fields.Datetime(string="Submission Date", default=fields.Datetime.now, tracking=True)
    delivery_days = fields.Integer(string="Delivery Lead Time (Days)", required=True, default=7, tracking=True)
    notes = fields.Text(string="Vendor Comments/Notes")
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected')
    ], string="State", default='draft', required=True, tracking=True)

    currency_id = fields.Many2one('res.currency', related='purchase_id.currency_id', string='Currency', readonly=True, store=True)
    total_amount = fields.Monetary(string="Total Bid Amount", compute="_compute_total_amount", currency_field='currency_id', store=True, tracking=True)
    line_ids = fields.One2many('vendor.quotation.line', 'quotation_id', string="Quotation Lines", copy=True)

    # Vendor metrics for comparison view
    vendor_rating = fields.Float(related='vendor_id.vendor_rating', string="Vendor Rating", readonly=True)
    on_time_percentage = fields.Float(related='vendor_id.on_time_percentage', string="Vendor On-time (%)", readonly=True)

    is_lowest_price = fields.Boolean(string="Is Lowest Price", compute="_compute_comparison_indicators")
    is_best_vendor = fields.Boolean(string="Is Best Vendor", compute="_compute_comparison_indicators")

    @api.depends('total_amount', 'purchase_id.quotation_ids.total_amount', 'vendor_id.vendor_rating')
    def _compute_comparison_indicators(self):
        for quotation in self:
            siblings = quotation.purchase_id.quotation_ids.filtered(lambda q: q.state in ('submitted', 'accepted', 'draft'))
            if not siblings:
                quotation.is_lowest_price = False
                quotation.is_best_vendor = False
                continue

            # Lowest price logic
            amounts = siblings.mapped('total_amount')
            min_amount = min(amounts) if amounts else 0.0
            quotation.is_lowest_price = (quotation.total_amount == min_amount) if min_amount > 0 else False

            # Best vendor logic (highest rating)
            ratings = siblings.mapped('vendor_rating')
            max_rating = max(ratings) if ratings else 0.0
            quotation.is_best_vendor = (quotation.vendor_rating == max_rating) if max_rating > 0 else False

    @api.depends('line_ids.subtotal')
    def _compute_total_amount(self):
        for quotation in self:
            quotation.total_amount = sum(quotation.line_ids.mapped('subtotal'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('vendor.quotation') or 'New'
        return super().create(vals_list)

    def action_submit(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'submitted'
                # Log in history with sudo
                self.env['approval.history'].sudo().create({
                    'purchase_id': record.purchase_id.id,
                    'user_id': self.env.user.id,
                    'action': 'Vendor Submitted Quote',
                    'remark': _("Vendor %s submitted quotation %s for %s %s") % (record.vendor_id.name, record.name, record.total_amount, record.currency_id.symbol),
                    'date': fields.Datetime.now(),
                })
                # RFQ state automatically moves to under_review if currently pending_vendor_bid (using sudo for state write)
                if record.purchase_id.hackathon_state in ('draft', 'pending_vendor_bid'):
                    record.purchase_id.sudo().hackathon_state = 'under_review'
                # Send mail notification and post chatter with sudo
                record.sudo()._notify_quotation_submitted()

    def action_accept(self):
        for record in self:
            record.state = 'accepted'

    def action_reject(self):
        for record in self:
            record.state = 'rejected'

    def _notify_quotation_submitted(self):
        template = self.env.ref('procurement_vendor_management.email_template_quotation_submitted', raise_if_not_found=False)
        if template:
            # Send notification to procurement officers / managers
            group_officers = self.env.ref('procurement_vendor_management.group_procurement_officer')
            recipients = group_officers.users.mapped('partner_id')
            for recipient in recipients:
                template.send_mail(self.id, force_send=True, email_values={'email_to': recipient.email})
            # Also log in purchase order chatter
            self.purchase_id.message_post(body=_("New Vendor Quotation %s submitted by %s for amount %s %s.") % (self.name, self.vendor_id.name, self.total_amount, self.currency_id.symbol))
