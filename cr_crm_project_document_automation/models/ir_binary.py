# -*- coding: utf-8 -*-
from odoo import models
from odoo.http import request

class IrBinary(models.AbstractModel):
    _inherit = 'ir.binary'

    def _get_stream_from(self, record, field_name='raw', filename=None, filename_field='name', mimetype=None,
                         default_mimetype='application/octet-stream'):
        """
        Override to ensure documents use their intended name during download.
        Adapted from the Everest customization module.
        """
        if record._name == 'documents.document' and filename is None:
            # Case 1: Bulk download (ZIP) via custom controller
            shortcut_map = getattr(request, '_documents_shortcut_map', {})
            if record.id in shortcut_map:
                filename = shortcut_map[record.id]
            
            # Case 2: Single download (standard Document app behavior)
            if not filename:
                try:
                    path = request.httprequest.path
                    if path.startswith('/documents/content/'):
                        access_token = path.split('/')[-1]
                        Doc = request.env['documents.document']
                        # Odoo 18 token format handling
                        document_token, __, encoded_id = access_token.rpartition('o')
                        if document_token and encoded_id:
                            document_id = int(encoded_id, 16)
                            original_doc = Doc.sudo().browse(document_id)
                            # If we are downloading via a shortcut record, use the shortcut's name
                            if original_doc.exists() and original_doc.shortcut_document_id == record:
                                filename = original_doc.name
                except Exception:
                    pass

        return super(IrBinary, self)._get_stream_from(
            record, field_name, filename, filename_field, mimetype, default_mimetype)
