# -*- coding: utf-8 -*-
# Part of Creyox Technologies.

from odoo import models,fields

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
        print(self)
        print(self.original_record)
        print(self.duplicate_record)
