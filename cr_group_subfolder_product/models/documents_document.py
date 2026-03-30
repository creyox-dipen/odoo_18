# -*- coding: utf-8 -*-
# Part of Creyox Technologies

from odoo import fields, models, api, _


class DocumentsDocument(models.Model):
    """
    Extends documents.document to add a helper for safe folder deletion.

    The _cr_safe_delete_folder method recursively checks whether a folder
    or any of its descendants contain actual documents (non-folder records).
    If yes, the folder is preserved. If no documents are found anywhere in
    the subtree, the entire folder hierarchy is deleted.
    """

    _inherit = 'documents.document'

    cr_category_folder_line_id = fields.Many2one(
        'cr.category.folder.line',
        string='Category Folder Line',
        ondelete='set null',
        index=True,
        help='References the category folder line that created this folder.',
    )
    cr_is_product_root = fields.Boolean(
        string='Is Product Root Folder',
        default=False,
        help='True for the auto-created root folder that wraps all line folders for a product.',
    )

    def _cr_has_documents(self):
        """
        Recursively check whether this folder or any of its descendants
        contain any non-folder documents (i.e. actual files or links).

        :return: bool — True if any document exists in this subtree
        """
        self.ensure_one()
        # Check direct non-folder children (actual documents)
        non_folder_children = self.children_ids.filtered(
            lambda d: d.type != 'folder' and not d.shortcut_document_id
        )
        if non_folder_children:
            return True
        # Recurse into sub-folders
        sub_folders = self.children_ids.filtered(lambda d: d.type == 'folder')
        for sub in sub_folders:
            if sub._cr_has_documents():
                return True
        return False

    def _cr_safe_delete_folder(self):
        """
        Safely delete this folder and all its sub-folders if none of them
        contain any documents. If any document is found anywhere in the
        subtree, the entire subtree is preserved.

        This method is called when a folder line is removed from the
        product category's folder_structure_ids.
        """
        self.ensure_one()
        if self._cr_has_documents():
            # Do not delete — documents exist in this folder tree
            return
        # Recursively delete sub-folders first (safe to delete)
        for child in self.children_ids.filtered(lambda d: d.type == 'folder'):
            child._cr_safe_delete_folder()
        # Now delete self (no documents in subtree)
        self.unlink()
