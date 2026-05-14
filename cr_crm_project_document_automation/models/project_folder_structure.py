# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import fields, models, api, _
import re
from odoo.exceptions import ValidationError, UserError


class ProjectFolderStructure(models.Model):
    """Persistent storage for the global folder structure template."""

    _name = "project.folder.structure"
    _description = "Project Folder Structure Template"
    _order = "sequence asc"

    name = fields.Char(string="Folder Name", required=True)
    sequence = fields.Char(
        string="Sequence",
        required=True,
        help="Use dot notation: 1.0 = top-level, 1.1 = child of 1.0, etc.",
    )
    is_selected = fields.Boolean(string="Select", default=False)

    @api.constrains("sequence")
    def _check_sequence_format(self):
        """Ensure sequence only contains digits and dots."""
        for line in self:
            if not line.sequence:
                continue
            if not re.match(r"^\d+(\.\d+)*$", line.sequence):
                raise ValidationError(
                    _(
                        "Invalid sequence format: '%s'. "
                        "Only digits and dots are allowed (e.g., 1.0, 1.1.1)."
                    )
                    % line.sequence
                )

    def _get_normalized_sequence(self):
        """Reused normalization logic from the reference module."""
        self.ensure_one()
        if not self.sequence:
            return ()
        parts = []
        for p in self.sequence.split("."):
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

    def _get_descendant_lines(self):
        """Find all lines that are children or grandchildren of this line."""
        self.ensure_one()
        norm_seq = self._get_normalized_sequence()
        all_lines = self.search([])
        return all_lines.filtered(
            lambda l: l.id != self.id
            and l._get_normalized_sequence()[: len(norm_seq)] == norm_seq
        )

    def _cr_has_any_documents(self):
        """Recursive check: used to protect the hierarchy from deletion."""
        self.ensure_one()
        folders = (
            self.env["documents.document"]
            .sudo()
            .search(
                [
                    ("cr_project_folder_line_id", "=", self.id),
                ]
            )
        )
        return any(f._cr_has_documents() for f in folders)

    def _cr_has_direct_documents_anywhere(self):
        """Direct check: used ONLY for the warning message UI."""
        self.ensure_one()
        folders = (
            self.env["documents.document"]
            .sudo()
            .search(
                [
                    ("cr_project_folder_line_id", "=", self.id),
                ]
            )
        )
        return any(f._cr_has_direct_documents() for f in folders)

    @api.model
    def apply_structure_to_folder(self, cd_folder, mapping_only=False):
        """
        Builds the hierarchy and links documents to template lines.
        Can be called from Wizards or Automation (Sale Orders).
        """
        template_lines = self.search([], order="sequence asc")
        seq_to_doc = {}
        for line in template_lines:
            normalized_seq = line._get_normalized_sequence()
            parent_seq = line._get_parent_sequence()
            target_parent = cd_folder
            if parent_seq:
                target_parent = seq_to_doc.get(parent_seq, cd_folder)

            # Try to find existing folder by line ID first
            existing = self.env["documents.document"].search(
                [
                    ("cr_project_folder_line_id", "=", line.id),
                    ("folder_id", "=", target_parent.id),
                ],
                limit=1,
            )

            if not existing:
                # Map by name fallback
                existing = self.env["documents.document"].search(
                    [
                        ("name", "=", line.name),
                        ("folder_id", "=", target_parent.id),
                        ("type", "=", "folder"),
                    ],
                    limit=1,
                )
                if existing:
                    existing.cr_project_folder_line_id = line.id

            if not existing and not mapping_only:
                existing = self.env["documents.document"].create(
                    {
                        "name": line.name,
                        "folder_id": target_parent.id,
                        "type": "folder",
                        "company_id": cd_folder.company_id.id,
                        "is_master_folder": True,
                        "cr_project_folder_line_id": line.id,
                    }
                )

            if existing:
                seq_to_doc[normalized_seq] = existing


class ProjectFolderStructureWizard(models.TransientModel):
    """The wizard popup for editing and creating folders."""

    _name = "project.folder.structure.wizard"
    _description = "Project Folder Structure Wizard"

    line_ids = fields.One2many(
        "project.folder.structure.wizard.line",
        "wizard_id",
        string="Folder Structure Lines",
    )

    @api.model
    def default_get(self, fields):
        res = super(ProjectFolderStructureWizard, self).default_get(fields)
        template_lines = self.env["project.folder.structure"].search(
            [], order="sequence asc"
        )
        line_vals = []
        for line in template_lines:
            line_vals.append(
                (
                    0,
                    0,
                    {
                        "line_id": line.id,
                        "name": line.name,
                        "sequence": line.sequence,
                        "is_selected": line.is_selected,
                    },
                )
            )
        res.update({"line_ids": line_vals})
        return res

    def action_create_folders(self):
        """Save structure and apply/sync folders to all projects."""
        self._save_lines()
        customer_data_folders = self.env["documents.document"].search(
            [("name", "=", "Customer Data"), ("type", "=", "folder")]
        )
        for cd_folder in customer_data_folders:
            self.env["project.folder.structure"].apply_structure_to_folder(cd_folder)
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_delete_selected(self):
        """Safe deletion logic."""
        self._save_lines()

        customer_data_folders = self.env["documents.document"].search(
            [("name", "=", "Customer Data"), ("type", "=", "folder")]
        )
        for cd_folder in customer_data_folders:
            self.env["project.folder.structure"].apply_structure_to_folder(
                cd_folder, mapping_only=True
            )

        selected_lines = self.env["project.folder.structure"].search(
            [("is_selected", "=", True)]
        )
        if not selected_lines:
            raise UserError(_("Please select at least one line to delete."))

        candidates = selected_lines
        for line in selected_lines:
            candidates |= line._get_descendant_lines()

        lines_with_direct_files = candidates.filtered(
            lambda l: l._cr_has_direct_documents_anywhere()
        )
        has_any_files = any(l._cr_has_any_documents() for l in selected_lines)

        if has_any_files:
            names = ", ".join(lines_with_direct_files.mapped("name")) or _(
                "sub-folders"
            )
            message = (
                _(
                    "The following folders contain files in some projects: %s. \n\nDo you want to proceed? Only empty folders will be deleted."
                )
                % names
            )

            return {
                "name": _("Safe Delete Warning"),
                "type": "ir.actions.act_window",
                "res_model": "cr.folder.delete.warning",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_message": message,
                    "default_line_ids": [fields.Command.set(candidates.ids)],
                },
            }

        self._perform_deletion(candidates)
        return {"type": "ir.actions.client", "tag": "reload"}

    def _save_lines(self):
        """Update existing lines instead of unlinking everything to preserve IDs."""
        wizard_line_ids = [l.line_id for l in self.line_ids if l.line_id]
        self.env["project.folder.structure"].search(
            [("id", "not in", wizard_line_ids)]
        ).unlink()

        for line in self.line_ids:
            vals = {
                "name": line.name,
                "sequence": line.sequence,
                "is_selected": line.is_selected,
            }
            if line.line_id:
                rec = self.env["project.folder.structure"].browse(line.line_id)
                if rec.exists():
                    rec.write(vals)
                else:
                    new_line = self.env["project.folder.structure"].create(vals)
                    line.line_id = new_line.id
            else:
                new_line = self.env["project.folder.structure"].create(vals)
                line.line_id = new_line.id

    def _perform_deletion(self, lines):
        """Delete folders in projects and then the template lines."""
        folders = (
            self.env["documents.document"]
            .sudo()
            .search([("cr_project_folder_line_id", "in", lines.ids)])
        )
        for folder in folders:
            folder._cr_safe_delete_folder()
        lines.unlink()


class ProjectFolderStructureWizardLine(models.TransientModel):
    _name = "project.folder.structure.wizard.line"
    _description = "Wizard Structure Line"

    wizard_id = fields.Many2one("project.folder.structure.wizard")
    line_id = fields.Integer(string="Original Line ID")
    name = fields.Char(string="Folder Name", required=True)
    sequence = fields.Char(string="Sequence", required=True)
    is_selected = fields.Boolean(string="Select")

    @api.constrains("sequence")
    def _check_sequence_format(self):
        for line in self:
            if not line.sequence:
                continue
            if not re.match(r"^\d+(\.\d+)*$", line.sequence):
                raise ValidationError(_("Invalid sequence format."))


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    cr_project_folder_line_id = fields.Many2one(
        "project.folder.structure",
        string="Project Folder Line",
        ondelete="set null",
        index=True,
    )

    def _cr_has_direct_documents(self):
        """Check if this specific folder instance contains files."""
        self.ensure_one()
        return any(
            d.type != "folder" and not d.shortcut_document_id for d in self.children_ids
        )

    def _cr_has_documents(self):
        self.ensure_one()
        if self._cr_has_direct_documents():
            return True
        for sub in self.children_ids.filtered(lambda d: d.type == "folder"):
            if sub._cr_has_documents():
                return True
        return False

    def _cr_safe_delete_folder(self):
        self.ensure_one()
        if self._cr_has_documents():
            return
        for child in self.children_ids.filtered(lambda d: d.type == "folder"):
            child._cr_safe_delete_folder()
        self.unlink()
