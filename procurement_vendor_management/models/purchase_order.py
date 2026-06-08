# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    hackathon_state = fields.Selection([
        ('draft', 'Draft RFQ'),
        ('pending_vendor_bid', 'Pending Vendor Bid'),
        ('under_review', 'Under Review'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('po_created', 'PO Created')
    ], string="Procurement Status", default='draft', required=True, tracking=True)

    approval_remark = fields.Text(string="Approval Remark", tracking=True)
    approved_vendor_id = fields.Many2one('res.partner', string="Approved Vendor", tracking=True)
    selected_quotation_id = fields.Many2one('vendor.quotation', string="Selected Winning Quotation", domain="[('purchase_id', '=', id), ('state', '=', 'submitted')]", tracking=True)

    invited_vendor_ids = fields.Many2many(
        'res.partner',
        'purchase_order_invited_partner_rel',
        'order_id',
        'partner_id',
        string="Invited Vendors",
        help="Vendors invited to submit quotations for this RFQ."
    )

    quotation_ids = fields.One2many('vendor.quotation', 'purchase_id', string="Vendor Quotations")
    quotation_count = fields.Integer(string="Quotations Count", compute="_compute_quotation_count")

    approval_history_ids = fields.One2many('approval.history', 'purchase_id', string="Approval History")
    approval_history_count = fields.Integer(string="Approval History Count", compute="_compute_approval_history_count")

    @api.depends('quotation_ids')
    def _compute_quotation_count(self):
        for order in self:
            order.quotation_count = len(order.quotation_ids)

    @api.depends('approval_history_ids')
    def _compute_approval_history_count(self):
        for order in self:
            order.approval_history_count = len(order.approval_history_ids)

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            order._create_history_record('RFQ Created', _("RFQ created by %s.") % self.env.user.name)
        return orders

    def _create_history_record(self, action, remark):
        self.env['approval.history'].create({
            'purchase_id': self.id,
            'user_id': self.env.user.id,
            'action': action,
            'remark': remark,
            'date': fields.Datetime.now(),
        })

    def action_send_rfq_custom(self):
        self.ensure_one()
        if self.hackathon_state != 'draft':
            raise UserError(_("You can only send an RFQ that is in draft state."))
        
        self.hackathon_state = 'pending_vendor_bid'
        all_vendors = self.partner_id | self.invited_vendor_ids
        self._create_history_record('RFQ Sent', _("RFQ sent to invited vendors: %s.") % ", ".join(all_vendors.mapped('name')))
        
        # Send mail notifications
        self._notify_invited_vendors()

    def action_request_approval(self):
        self.ensure_one()
        if self.hackathon_state != 'under_review':
            raise UserError(_("You can only request approval when the RFQ is under review."))
        
        if not self.selected_quotation_id:
            raise UserError(_("Please select a winning vendor quotation before requesting approval."))

        self.hackathon_state = 'pending_approval'
        self._create_history_record('Approval Requested', _("Procurement approval requested by %s. Selected Quotation: %s (Vendor: %s, Amount: %s %s).") % (
            self.env.user.name,
            self.selected_quotation_id.name,
            self.selected_quotation_id.vendor_id.name,
            self.selected_quotation_id.total_amount,
            self.selected_quotation_id.currency_id.symbol
        ))
        
        # Send mail to Managers
        self._notify_managers_approval_request()

    def action_create_po_custom(self):
        self.ensure_one()
        if self.hackathon_state != 'approved':
            raise UserError(_("Purchase Order can only be generated for approved procurements."))
        
        if not self.selected_quotation_id:
            raise UserError(_("No quotation selected. Please select an approved vendor quotation first."))

        # 1. Update Partner to winning Vendor
        winning_quotation = self.selected_quotation_id
        self.partner_id = winning_quotation.vendor_id
        self.approved_vendor_id = winning_quotation.vendor_id

        # 2. Re-create PO lines matching the winning quotation lines
        self.order_line.unlink()
        po_lines = []
        for line in winning_quotation.line_ids:
            po_lines.append((0, 0, {
                'order_id': self.id,
                'product_id': line.product_id.id,
                'product_qty': line.quantity,
                'price_unit': line.price_unit,
                'name': line.product_id.display_name or line.product_id.name,
                'date_planned': fields.Datetime.now() + timedelta(days=winning_quotation.delivery_days),
            }))
        self.order_line = po_lines

        # 3. Transition states
        self.hackathon_state = 'po_created'
        winning_quotation.state = 'accepted'
        
        # Reject other quotations
        other_quotations = self.quotation_ids.filtered(lambda q: q.id != winning_quotation.id)
        other_quotations.write({'state': 'rejected'})

        # 4. Trigger standard Odoo PO flow (button_confirm)
        self.button_confirm()

        # 5. Log and notify
        self._create_history_record('PO Generated', _("Purchase Order generated and confirmed from quotation %s. Winning Vendor: %s, Amount: %s %s.") % (
            winning_quotation.name,
            winning_quotation.vendor_id.name,
            winning_quotation.total_amount,
            winning_quotation.currency_id.symbol
        ))

        # Send PO confirmation email
        self._notify_po_created()

    # --- Email Notification Triggers ---
    def _notify_invited_vendors(self):
        template = self.env.ref('procurement_vendor_management.email_template_rfq_invitation', raise_if_not_found=False)
        if template:
            all_vendors = self.partner_id | self.invited_vendor_ids
            for vendor in all_vendors:
                if vendor.email:
                    # Generate the email values from template manually to bypass Odoo standard partner/recipients fallback logic
                    rendered = template.with_context(
                        email_to=vendor.email,
                        partner_id=vendor.id
                    )._generate_template([self.id], ['subject', 'body_html', 'email_from'])
                    values = rendered.get(self.id, {})
                    
                    # Force recipients
                    values.update({
                        'email_to': vendor.email,
                        'partner_ids': [(6, 0, [vendor.id])],
                        'recipient_ids': [(6, 0, [vendor.id])],
                        'res_id': self.id,
                        'model': 'purchase.order',
                        'body': values.get('body_html', ''),
                    })
                    if 'partner_to' in values:
                        values.pop('partner_to')
                    
                    # Create and send the mail directly
                    mail = self.env['mail.mail'].sudo().create(values)
                    mail.send()

    def _notify_managers_approval_request(self):
        template = self.env.ref('procurement_vendor_management.email_template_approval_request', raise_if_not_found=False)
        if template:
            group_managers = self.env.ref('procurement_vendor_management.group_procurement_manager')
            recipients = group_managers.users.mapped('partner_id')
            for recipient in recipients:
                if recipient.email:
                    template.with_context(email_to=recipient.email).send_mail(self.id, force_send=True, email_values={'email_to': recipient.email})

    def _notify_po_created(self):
        template = self.env.ref('procurement_vendor_management.email_template_po_created', raise_if_not_found=False)
        if template:
            if self.partner_id.email:
                template.with_context(email_to=self.partner_id.email).send_mail(self.id, force_send=True, email_values={'email_to': self.partner_id.email})

    def _notify_approval_approved(self):
        template = self.env.ref('procurement_vendor_management.email_template_approval_approved', raise_if_not_found=False)
        if template:
            # Send notification back to the procurement officer who raised the request (user_id)
            if self.user_id.partner_id.email:
                template.with_context(email_to=self.user_id.partner_id.email).send_mail(self.id, force_send=True, email_values={'email_to': self.user_id.partner_id.email})

    def _notify_approval_rejected(self):
        template = self.env.ref('procurement_vendor_management.email_template_approval_rejected', raise_if_not_found=False)
        if template:
            if self.user_id.partner_id.email:
                template.with_context(email_to=self.user_id.partner_id.email).send_mail(self.id, force_send=True, email_values={'email_to': self.user_id.partner_id.email})

    def action_approve_wizard(self):
        self.ensure_one()
        return {
            'name': _('Approve RFQ'),
            'type': 'ir.actions.act_window',
            'res_model': 'approval.remark.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_id': self.id,
                'default_action': 'approve',
            }
        }

    def action_reject_wizard(self):
        self.ensure_one()
        return {
            'name': _('Reject RFQ'),
            'type': 'ir.actions.act_window',
            'res_model': 'approval.remark.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_id': self.id,
                'default_action': 'reject',
            }
        }


