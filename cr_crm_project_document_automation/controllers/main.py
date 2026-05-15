# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo.addons.documents.controllers.documents import ShareRoute
from odoo.http import request, content_disposition
from odoo.exceptions import MissingError
import io
import zipfile
import pathlib
from collections import defaultdict
from typing import NamedTuple

class ShareRouteCustom(ShareRoute):

    def _make_zip(self, name, documents):
        """
        Override to ensure shortcuts use their own name instead of target name in the zip,
        while still containing the original file content.
        """
        class Item(NamedTuple):
            path: str
            content: str

        seen_folders = set()
        seen_names = defaultdict(int)

        def unique(pathname):
            seen_names[pathname] += 1
            if seen_names[pathname] <= 1:
                return pathname
            ext = ''.join(pathlib.Path(pathname).suffixes)
            return f'{pathname.removesuffix(ext)}-{seen_names[pathname]}{ext}'

        def make_zip_item(document, folder):
            if document.type == 'url':
                raise ValueError("cannot create a zip item out of an url")
            if document.type == 'folder':
                return Item(unique(f'{folder.path}{document.name}') + '/', '')
            try:
                # Key Fix: Get the content from the TARGET (original) but use the shortcut's name
                # This ensures the ZIP contains the real file, not the 1KB placeholder.
                stream = self._documents_content_stream(document.shortcut_document_id or document)
                download_name = document.name
                content = stream.read()
            except (ValueError, MissingError, OSError, FileNotFoundError):
                return None
            return Item(unique(f'{folder.path}{download_name}'), content)

        def generate_zip_items(documents_sudo, folder):
            documents_sudo = documents_sudo.sorted(lambda d: d.id)

            yield from (
                item
                for doc in documents_sudo
                if doc.type == 'binary' and (doc.shortcut_document_id or doc).attachment_id
                if (item := make_zip_item(doc, folder)) is not None
            )
            for folder_sudo in documents_sudo:
                if folder_sudo.type != 'folder' or folder_sudo in seen_folders:
                    continue
                seen_folders.add(folder_sudo)

                if (sub_folder := make_zip_item(folder_sudo, folder)) is not None:
                    yield sub_folder
                    for sub_document_sudo in self._get_folder_children(folder_sudo):
                        yield from generate_zip_items(sub_document_sudo, sub_folder)

        stream = io.BytesIO()
        root_folder = Item('', '')
        try:
            with zipfile.ZipFile(stream, 'w') as doc_zip:
                for (path, content) in generate_zip_items(documents, root_folder):
                    doc_zip.writestr(path, content, compress_type=zipfile.ZIP_DEFLATED)
        except zipfile.BadZipfile:
            pass

        content = stream.getvalue()
        headers = [
            ('Content-Type', 'zip'),
            ('X-Content-Type-Options', 'nosniff'),
            ('Content-Length', len(content)),
            ('Content-Disposition', content_disposition(name))
        ]
        return request.make_response(content, headers)
