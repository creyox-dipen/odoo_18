# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models,fields
from odoo.exceptions import UserError

class MergeMenuWiz(models.TransientModel):
    _name= "merge.menu.wiz"
    _description = "merge menu in settings wizard"

    actions = fields.Selection([
        ('none', 'None'),
        ('delete', 'Delete'),
        ('archive', 'Archive')
    ], string="Action on Duplicate Records", default='none')

    original_record = fields.Reference(
        selection=lambda self: [(m.model, m.name) for m in self.env['ir.model'].search([])],
    )
    duplicate_record = fields.Reference(
        selection=lambda self: [(m.model, m.name) for m in self.env['ir.model'].search([])],
    )

    def merge_records(self):

        # Step 1: Identify master + duplicates
        original = self.original_record
        duplicate = self.duplicate_record

        if not original:
            raise UserError("Please select one record as Original.")

        # FIX: record_id is already an int
        master_id = original.id
        duplicate_id = duplicate.ids
        print(master_id)
        print(duplicate_id)
        # Step 2: Reassign references safely
        self.env['duplicate.wiz']._reassign_references('res.partner', master_id, duplicate_id)

        # Step 3: Apply chosen action to duplicates
        records = self.env['res.partner'].browse(duplicate_id)
        if self.actions == 'delete':
            records.unlink()
        elif self.actions == 'archive':
            records.write({'active': False})
