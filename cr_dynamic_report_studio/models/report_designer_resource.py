# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields
import base64
from io import BytesIO
from PIL import Image
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.image import image_data_uri


class ReportDesignerResource(models.Model):
    _name = "report.designer.resource"
    _description = "Image Library"

    name = fields.Char(string="Image Name", required=True)
    image = fields.Binary(string="Image", required=True, attachment=True)
    image_small = fields.Binary(string="Thumbnail", attachment=True)
    mime_type = fields.Char(string="MIME Type")
    file_size = fields.Integer(string="File Size (Bytes)")
    category = fields.Selection(
        [
            ("logo", "Logo"),
            ("background", "Background"),
            ("icon", "Icon"),
            ("other", "Other"),
        ],
        string="Category",
        default="other",
    )

    def get_image_uri(self):
        """Return the base64 data URI of the image, converting ICO/WEBP to PNG/JPG if necessary."""
        self.ensure_one()
        # Force bin_size=False to retrieve actual binary data instead of file size string
        img_data = self.with_context(bin_size=False).image
        if not img_data:
            return ""

        try:
            raw_bytes = base64.b64decode(img_data)
        except Exception:
            raw_bytes = img_data

        mimetype = guess_mimetype(raw_bytes, "")

        # Convert ICO format to PNG to ensure browser and wkhtmltopdf compatibility
        if mimetype in (
            "image/x-icon",
            "image/vnd.microsoft.icon",
        ) or raw_bytes.startswith(b"\x00\x00\x01\x00"):
            try:
                img = Image.open(BytesIO(raw_bytes))
                # Extract the largest sub-image in case of multi-size ICO files to preserve high resolution and transparency
                if hasattr(img, "ico"):
                    sizes = img.ico.sizes()
                    if sizes:
                        largest_size = max(sizes, key=lambda s: s[0] * s[1])
                        img = img.ico.getimage(largest_size)
                out_buf = BytesIO()
                img.convert("RGBA").save(out_buf, format="PNG")
                raw_bytes = out_buf.getvalue()
            except Exception:
                pass

        return image_data_uri(base64.b64encode(raw_bytes))
