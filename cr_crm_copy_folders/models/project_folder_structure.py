# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
import re
from odoo.exceptions import ValidationError

class ProjectFolderStructure(models.Model):
    """Persistent storage for the global folder structure template."""
    _name = 'project.folder.structure'
    _description = 'Project Folder Structure Template'
    _order = 'sequence asc'
    # Forced reload for security sync

    name = fields.Char(string='Folder Name', required=True)
    sequence = fields.Char(
        string='Sequence', 
        required=True, 
        help="Use dot notation: 1.0 = top-level, 1.1 = child of 1.0, etc."
    )

    @api.constrains('sequence')
    def _check_sequence_format(self):
        """Ensure sequence only contains digits and dots."""
        for line in self:
            if not line.sequence:
                continue
            if not re.match(r'^\d+(\.\d+)*$', line.sequence):
                raise ValidationError(_(
                    "Invalid sequence format: '%s'. "
                    "Only digits and dots are allowed (e.g., 1.0, 1.1.1)."
                ) % line.sequence)

    def _get_normalized_sequence(self):
        """Reused normalization logic from the reference module."""
        self.ensure_one()
        if not self.sequence:
            return ()
        parts = []
        for p in self.sequence.split('.'):
            p_trimmed = p.strip()
            if not p_trimmed:
                continue
            try:
                parts.append(int(p_trimmed))
            except ValueError:
                parts.append(p_trimmed)
        while len(parts) > 1 and parts[-1] == 0:
            parts.pop()
        return tuple(parts)

    def _get_parent_sequence(self):
        """Determine the parent's normalized sequence."""
        norm_seq = self._get_normalized_sequence()
        if len(norm_seq) <= 1:
            return None
        return norm_seq[:-1]

class ProjectFolderStructureWizard(models.TransientModel):
    """The wizard popup for editing and creating folders."""
    _name = 'project.folder.structure.wizard'
    _description = 'Project Folder Structure Wizard'

    line_ids = fields.One2many(
        'project.folder.structure.wizard.line', 
        'wizard_id', 
        string='Folder Structure Lines'
    )

    @api.model
    def default_get(self, fields):
        res = super(ProjectFolderStructureWizard, self).default_get(fields)
        # Load existing saved template lines into the wizard
        template_lines = self.env['project.folder.structure'].search([], order='sequence asc')
        line_vals = []
        for line in template_lines:
            line_vals.append((0, 0, {
                'name': line.name,
                'sequence': line.sequence,
            }))
        res.update({'line_ids': line_vals})
        return res

    def action_create_folders(self):
        """Save the structure and apply it to all Customer Data folders."""
        # 1. Clear and Save the new structure to persistent storage
        self.env['project.folder.structure'].search([]).unlink()
        for line in self.line_ids:
            self.env['project.folder.structure'].create({
                'name': line.name,
                'sequence': line.sequence,
            })

        # 2. Find all "Customer Data" folders in the system
        customer_data_folders = self.env['documents.document'].search([
            ('name', '=', 'Customer Data'),
            ('type', '=', 'folder')
        ])

        # 3. Apply the structure to each "Customer Data" folder
        for cd_folder in customer_data_folders:
            self._apply_structure_to_folder(cd_folder)

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _apply_structure_to_folder(self, cd_folder):
        """Core logic to build the hierarchy inside a target folder."""
        template_lines = self.env['project.folder.structure'].search([], order='sequence asc')
        seq_to_doc = {}
        
        for line in template_lines:
            normalized_seq = line._get_normalized_sequence()
            parent_seq = line._get_parent_sequence()
            
            # Determine the parent folder (either Customer Data or a parent from the template)
            target_parent = cd_folder
            if parent_seq:
                target_parent = seq_to_doc.get(parent_seq, cd_folder)

            # Check if this specific template folder already exists in this location
            existing = self.env['documents.document'].search([
                ('name', '=', line.name),
                ('folder_id', '=', target_parent.id),
                ('type', '=', 'folder')
            ], limit=1)

            if not existing:
                # Create the folder using the same company and settings
                doc = self.env['documents.document'].create({
                    'name': line.name,
                    'folder_id': target_parent.id,
                    'type': 'folder',
                    'company_id': cd_folder.company_id.id,
                    'is_master_folder': True,
                })
            else:
                doc = existing
            
            # Store the created folder in the sequence map for its children to find
            seq_to_doc[normalized_seq] = doc

class ProjectFolderStructureWizardLine(models.TransientModel):
    """Transient lines for the wizard list view."""
    _name = 'project.folder.structure.wizard.line'
    _description = 'Wizard Structure Line'

    wizard_id = fields.Many2one('project.folder.structure.wizard')
    name = fields.Char(string='Folder Name', required=True)
    sequence = fields.Char(string='Sequence', required=True)

    @api.constrains('sequence')
    def _check_sequence_format(self):
        for line in self:
            if not line.sequence:
                continue
            if not re.match(r'^\d+(\.\d+)*$', line.sequence):
                raise ValidationError(_(
                    "Invalid sequence format: '%s'. "
                    "Only digits and dots are allowed (e.g., 1.0, 1.1.1)."
                ) % line.sequence)
