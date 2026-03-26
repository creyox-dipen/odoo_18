# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import fields, models, api
from odoo.exceptions import ValidationError


class CrCategoryFolderLine(models.Model):
    """
    One2many line on product.category that defines a folder template.

    Each line represents a node in the folder hierarchy.
    The 'sequence' field uses dot notation to express depth:
      - 1.0  => top-level folder
      - 1.1  => child of 1.0
      - 1.1.1 => child of 1.1
      - 2.0  => second top-level folder

    These lines are used to auto-create documents.document (type='folder')
    records for every product.template that belongs to this category.
    """

    _name = 'cr.category.folder.line'
    _description = 'Category Folder Line'
    _order = 'sequence asc'

    category_id = fields.Many2one(
        'product.category',
        string='Category',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Char(
        string='Sequence',
        required=True,
        help=(
            'Defines hierarchy using dot notation. '
            'Example: 1.0 = top-level, 1.1 = child of 1.0, 1.1.1 = child of 1.1'
        ),
    )
    name = fields.Char(
        string='Folder Name',
        required=True,
    )

    @api.constrains('sequence')
    def _check_sequence_unique_per_category(self):
        """Ensure sequence values are unique within the same category (normalized)."""
        for line in self:
            norm_seq = line._get_normalized_sequence()
            existing_lines = self.search([
                ('category_id', '=', line.category_id.id),
                ('id', '!=', line.id),
            ])
            for existing in existing_lines:
                if existing._get_normalized_sequence() == norm_seq:
                    raise ValidationError(
                        f"Sequence '{line.sequence}' (normalized: {norm_seq}) "
                        f"is logically the same as existing '{existing.sequence}'. "
                        "Each folder must have a unique hierarchy position."
                    )

    def _get_normalized_sequence(self):
        """
        Convert sequence string to a tuple of values, trimming trailing numeric zeros.
        Example: "1.0" -> (1,), "1.1" -> (1, 1), "1.1.0" -> (1, 1).

        :return: tuple of (int or str)
        """
        self.ensure_one()
        if not self.sequence:
            return ()
        parts = []
        for p in self.sequence.split('.'):
            p_trimmed = p.strip()
            if not p_trimmed:
                continue
            try:
                # Try to convert to int if it looks like a number
                parts.append(int(p_trimmed))
            except ValueError:
                parts.append(p_trimmed)

        # Trim trailing numeric zeros (if more than one part)
        # e.g. 1.0 -> 1, 1.1.0 -> 1.1
        while len(parts) > 1 and parts[-1] == 0:
            parts.pop()

        return tuple(parts)

    def _get_parent_sequence(self):
        """
        Return the parent normalized sequence tuple for this line.

        The parent is determined by removing the last segment of the normalized sequence.
        Example:
          - '1.1'   => parent is (1,)
          - '1.1.1' => parent is (1, 1)
          - '1.0'   => no parent (returns None)

        :return: tuple or None representing the parent normalized sequence
        """
        norm_seq = self._get_normalized_sequence()
        if len(norm_seq) <= 1:
            return None
        # Parent = sequence without last segment
        return norm_seq[:-1]

    def _get_descendant_lines(self):
        """
        Find all folder lines in the same category that are descendants of this line.
        Based on the normalized sequence dot-notation.
        """
        self.ensure_one()
        norm_seq = self._get_normalized_sequence()
        # Find all lines in the same category
        all_lines = self.search([('category_id', '=', self.category_id.id)])
        # Descendant if its normalized sequence starts with this line's sequence (and is longer)
        return all_lines.filtered(
            lambda l: l.id != self.id and l._get_normalized_sequence()[:len(norm_seq)] == norm_seq
        )

    def _cr_has_any_documents(self):
        """
        Check if this folder line has any documents on any product.
        """
        self.ensure_one()
        folders = self.env['documents.document'].sudo().search([
            ('cr_category_folder_line_id', '=', self.id),
        ])
        return any(f._cr_has_documents() for f in folders)
