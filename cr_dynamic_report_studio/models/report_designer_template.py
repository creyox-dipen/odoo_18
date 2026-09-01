# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from odoo import models, fields, api
import json
import re
import logging
import os
import shutil
import sys

_logger = logging.getLogger(__name__)

# Copy system fonts to static directory at import/startup time
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fonts_dir = os.path.join(addon_dir, "static", "src", "fonts")
os.makedirs(fonts_dir, exist_ok=True)

font_mappings = {
    "Arial": "arial.ttf",
    "Times New Roman": "times.ttf",
    "Courier New": "cour.ttf",
    "Verdana": "verdana.ttf",
    "Georgia": "georgia.ttf",
}

for name, filename in font_mappings.items():
    src_path = os.path.join(r"C:\Windows\Fonts", filename)
    dst_path = os.path.join(fonts_dir, filename)
    if os.path.exists(src_path) and not os.path.exists(dst_path):
        try:
            shutil.copy2(src_path, dst_path)
            _logger.info("[FONT SETUP] Copied %s to %s", filename, dst_path)
        except Exception as e:
            _logger.info("[FONT SETUP] Failed to copy font %s: %s", filename, e)


class ReportDesignerTemplate(models.Model):
    _name = "report.designer.template"
    _description = "Report Template"
    _order = "name"

    name = fields.Char(string="Template Name", required=True)
    model_id = fields.Many2one(
        "ir.model", string="Bound Model", required=True, ondelete="cascade"
    )
    model_name = fields.Char(
        related="model_id.model", string="Model Name", readonly=True, store=True
    )
    paper_size = fields.Selection(
        [
            ("a4", "A4"),
            ("a3", "A3"),
            ("letter", "Letter"),
            ("legal", "Legal"),
            ("custom", "Custom"),
        ],
        string="Paper Size",
        default="a4",
    )
    paper_width = fields.Float(string="Paper Width (mm)", default=210.0)
    paper_height = fields.Float(string="Paper Height (mm)", default=297.0)
    orientation = fields.Selection(
        [("portrait", "Portrait"), ("landscape", "Landscape")],
        string="Orientation",
        default="portrait",
    )
    margin_top = fields.Float(string="Margin Top (mm)", default=10.0)
    margin_bottom = fields.Float(string="Margin Bottom (mm)", default=10.0)
    margin_left = fields.Float(string="Margin Left (mm)", default=10.0)
    margin_right = fields.Float(string="Margin Right (mm)", default=10.0)
    template_json = fields.Text(string="Template JSON", default="{}")
    thumbnail = fields.Binary(string="Thumbnail", attachment=True)
    last_print_log_id = fields.Many2one(
        "report.designer.print.log",
        string="Last Print Log",
        compute="_compute_last_print_log_id",
        store=False,
    )
    is_active = fields.Boolean(string="Active", default=True)
    is_bound_to_print_menu = fields.Boolean(
        string="Appears in Print Menu", default=False
    )
    page_ids = fields.One2many(
        "report.designer.template.page", "template_id", string="Pages"
    )
    component_ids = fields.One2many(
        "report.designer.component", "template_id", string="Components"
    )
    report_action_id = fields.Many2one(
        "ir.actions.report", string="Report Action", ondelete="set null"
    )
    description = fields.Text(string="Internal Notes")
    category = fields.Selection(
        [
            ("invoice", "Invoice"),
            ("sales", "Sales"),
            ("delivery", "Delivery"),
            ("hr", "HR"),
            ("custom", "Custom"),
        ],
        string="Category",
        default="custom",
    )

    def _compute_last_print_log_id(self):
        for record in self:
            last_log = (
                self.env["report.designer.print.log"]
                .sudo()
                .search([("template_id", "=", record.id)], order="id desc", limit=1)
            )
            record.last_print_log_id = last_log.id if last_log else False

    def action_open_designer(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "report_designer_action",
            "params": {
                "template_id": self.id,
            },
        }

    def action_bind_print_menu(self):
        self.ensure_one()
        view_key = f"cr_dynamic_report_studio.report_designer_template_{self.id}"
        self.create_or_update_qweb_view()
        if not self.report_action_id:
            report_action = self.env["ir.actions.report"].create(
                {
                    "name": self.name,
                    "model": self.model_name,
                    "report_type": "qweb-pdf",
                    "report_name": view_key,
                    "report_file": view_key,
                    "binding_model_id": self.model_id.id,
                    "binding_type": "report",
                }
            )
            self.report_action_id = report_action.id
            self.is_bound_to_print_menu = True
        else:
            self.report_action_id.write(
                {
                    "report_name": view_key,
                    "report_file": view_key,
                }
            )
        self._update_paper_format()

    def action_unbind_print_menu(self):
        self.ensure_one()
        if self.report_action_id:
            self.report_action_id.unlink()
        self.is_bound_to_print_menu = False

    def action_preview_pdf(self, res_ids=None):
        self.ensure_one()
        view_key = f"cr_dynamic_report_studio.report_designer_template_{self.id}"
        self.create_or_update_qweb_view()
        if not self.report_action_id:
            self.action_bind_print_menu()
        else:
            self.report_action_id.write(
                {
                    "report_name": view_key,
                    "report_file": view_key,
                }
            )
        self._update_paper_format()

        if not res_ids:
            # Fallback to search first record for preview if none provided (e.g. from Kanban)
            model_model = self.model_id.model
            record = self.env[model_model].search([], limit=1)
            if not record:
                from odoo.exceptions import UserError

                raise UserError(
                    f"No records found for model {self.model_id.name} to generate a preview."
                )
            res_ids = [record.id]

        if res_ids:
            try:
                # Force evaluate report template rendering in HTML to check for runtime execution crashes
                self.env["ir.actions.report"]._render_qweb_html(view_key, res_ids)
            except Exception as e:
                err_msg = str(e)
                node_xml = ""
                # QWebException holds more specific fields
                if hasattr(e, "path") and getattr(e, "path"):
                    err_msg += f"\nPath: {e.path}"
                if hasattr(e, "html") and getattr(e, "html"):
                    node_xml = e.html[:300] + "..." if len(e.html) > 300 else e.html
                elif hasattr(e, "node") and getattr(e, "node") is not None:
                    try:
                        from lxml import etree

                        node_xml = etree.tostring(e.node, encoding="unicode")
                        node_xml = (
                            node_xml[:300] + "..." if len(node_xml) > 300 else node_xml
                        )
                    except Exception:
                        pass

                # Check for common rendering errors and suggest corrections
                suggestion = ""
                if "Unknown format code" in err_msg:
                    suggestion = "Data type mismatch: You are trying to apply a numeric/float format code (like :.2f) to a text string field (like doc.name). Format codes must match the field's data type."
                elif "NameError" in err_msg or "is not defined" in err_msg:
                    suggestion = "Undefined variable: Ensure all database fields are prefixed with 'doc.' (e.g. doc.name) or 'row.' inside loops."
                elif "division by zero" in err_msg:
                    suggestion = "Math error: division by zero. Wrap the math expression in a conditional check to ensure the denominator is not zero."
                elif "AttributeError" in err_msg:
                    suggestion = "Invalid field attribute: Double-check if the field name is spelled correctly and exists on the model."
                else:
                    suggestion = "Please check the syntax and data types of your custom expressions."

                return {
                    "error": True,
                    "message": err_msg,
                    "node": node_xml,
                    "suggestion": suggestion,
                }

        if self.report_action_id:
            docids_str = ",".join(map(str, res_ids))
            return {
                "type": "ir.actions.act_url",
                "url": f"/report/pdf/{self.report_action_id.report_name}/{docids_str}",
                "target": "new",
            }
        return False

    def _update_paper_format(self):
        """Configure the wkhtmltopdf paper format.

        All margins are set to 0 because our design uses absolute positioning
        from the page origin (0,0). Any non-zero margin would shift the origin
        and misalign all elements.
        """
        self.ensure_one()
        if not self.report_action_id:
            return

        orientation = self.orientation.capitalize() if self.orientation else "Portrait"

        paperformat = self.env["report.paperformat"].search(
            [("name", "=", f"Paperformat for Template {self.id}")], limit=1
        )

        import json

        try:
            data = json.loads(self.template_json or "{}")
        except Exception:
            data = {}

        # wkhtmltopdf margins are in mm.
        margin_top_mm = int(round(self.margin_top))
        margin_bottom_mm = int(round(self.margin_bottom))
        margin_left_mm = int(round(self.margin_left))
        margin_right_mm = int(round(self.margin_right))

        paperformat_vals = {
            "name": f"Paperformat for Template {self.id}",
            "format": "custom",
            "page_width": int(round(self.paper_width)),
            "page_height": int(round(self.paper_height)),
            "orientation": orientation,
            "margin_top": 0,
            "margin_bottom": 0,
            "margin_left": 0,
            "margin_right": 0,
            "header_line": False,
            "dpi": 96,
            "header_spacing": 0,
            "disable_shrinking": True,
        }

        if paperformat:
            paperformat.write(paperformat_vals)
        else:
            paperformat = self.env["report.paperformat"].create(paperformat_vals)

        if self.report_action_id.paperformat_id != paperformat:
            self.report_action_id.write(
                {
                    "paperformat_id": paperformat.id,
                }
            )

    # -------------------------------------------------------------------------
    # QWeb Compilation
    # -------------------------------------------------------------------------

    def _get_font_family_name(self, font_name):
        """Return the standard font family name directly, fallback mapping Helvetica to Arial."""
        if font_name == "Helvetica":
            return "Arial"
        return font_name

    def _compile_element(
        self,
        el,
        seg_offset_y,
        margin_top=0,
        margin_left=0,
        flow_y_offset=0,
        z_index=None,
    ):
        """Compile a single element dict into a list of QWeb XML lines.

        Coordinates use the SAME unit as the designer canvas (px at 72dpi).
        The page container is also sized in the same units, so proportions match.
        """
        lines = []
        el_type = el.get("type")
        el_x_raw = el.get("x", 0)
        el_y_raw = el.get("y", 0)
        el_w = el.get("width", 100)
        el_h = el.get("height", 100)
        el_style = el.get("style", {})

        # Rotation can be on element directly or inside style
        el_rot = el.get("rotation")
        if el_rot is None:
            el_rot = el_style.get("rotation", 0)

        # X-coordinate translation (relative to content container)
        el_x = el_x_raw - margin_left

        # Y-coordinate translation (relative to content container)
        if flow_y_offset > 0:
            el_y = el_y_raw - flow_y_offset - margin_top
        else:
            el_y = el_y_raw - seg_offset_y - margin_top

        # Outer container — absolute positioning with pt (1pt = 1/72 inch).
        # 595pt = 210mm = A4 width, so designer coordinates map 1:1 to pt.
        if el_type == "table":
            outer = [
                f"margin-left: {el_x}pt",
                f"width: {el_w}pt",
            ]
            if z_index is not None:
                outer.append(f"z-index: {z_index}")
        elif el_type == "watermark":
            page_h = int(round(self.paper_height * 2.83465))
            local_y = el_y_raw % page_h if page_h else el_y_raw
            local_y_shifted = local_y - margin_top

            outer = [
                "position: absolute",
                "left: 0pt",
                f"top: {local_y_shifted}pt",
                "width: 100%",
                f"height: {el_h}pt",
                "z-index: 9999",
                "text-align: center",
            ]

            # Watermark specific outer styles
            opacity = el_style.get("opacity", 0.18)
            outer.append(f"opacity: {opacity}")
            outer.append("pointer-events: none")

        else:
            outer = [
                "position: absolute",
                f"left: {el_x}pt",
                f"top: {el_y}pt",
                f"width: {el_w}pt",
                f"height: {el_h}pt",
            ]
            if z_index is not None:
                outer.append(f"z-index: {z_index}")

        if el_rot and el_type != "watermark":
            outer.append(
                f"transform: rotate({el_rot}deg); -webkit-transform: rotate({el_rot}deg);"
            )

        if el_type in ("text", "field"):
            lines.extend(self._compile_text_field(el, el_type, outer, el_style))

        elif el_type == "watermark":
            lines.extend(self._compile_watermark(el, outer, el_style))

        elif el_type == "image":
            lines.extend(self._compile_image(el, outer, el_style))

        elif el_type == "line":
            lines.extend(self._compile_line(el, outer, el_style, el_h))

        elif el_type in ("shape", "rectangle"):
            lines.extend(self._compile_shape(el, outer, el_style))

        elif el_type == "table":
            lines.extend(self._compile_table(el, outer, el_style))

        elif el_type == "barcode":
            symbology = el.get("symbology", "Code 128")
            if symbology == "QR Code":
                btype = "QR"
            elif symbology == "EAN-13":
                btype = "EAN13"
            else:
                btype = "Code128"
            lines.extend(self._compile_barcode(el, outer, el_style, barcode_type=btype))

        else:
            css = "; ".join(outer)
            lines.append(
                f'        <div style="{css}; border: 1pt solid #ccc; background: #fafafa;">{el_type}</div>'
            )

        return lines

    def _esc_expr(self, expr):
        """Escape double quotes inside expressions to prevent XML construction errors."""
        if not expr:
            return ""
        return str(expr).replace('"', "&quot;")

    def _is_valid_field_path(self, model_name, path):
        if not model_name or not path:
            return False
        if path.startswith("doc."):
            path = path[4:]
        elif path.startswith("row."):
            path = path[4:]

        parts = path.split(".")
        try:
            current_model = self.env[model_name]
            for part in parts:
                if not part or not part[0].isalpha():
                    return False
                if part not in current_model._fields:
                    return False
                field = current_model._fields[part]
                if field.relational:
                    current_model = self.env[field.comodel_name]
            return True
        except Exception:
            return False

    def _is_expression_valid(self, model_name, expression):
        if not expression:
            return True
        if expression.strip() in (
            "current_date",
            "current_time",
            "current_datetime",
            "page_number",
            "total_pages",
            "page_count",
            "base_url",
        ):
            return True
        try:
            compile(expression, "<string>", "eval")
        except Exception:
            return False

        import re

        paths = re.findall(r"\b(?:doc|row)\.([a-zA-Z0-9_.]+)", expression)
        if not paths:
            if re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", expression.strip()):
                return self._is_valid_field_path(model_name, expression.strip())
            return True

        for path in paths:
            # Skip special helper methods
            clean_path = ".".join(
                [
                    p
                    for p in path.split(".")
                    if p not in ("filtered", "mapped", "sorted", "filtered_domain")
                ]
            )
            if clean_path and not self._is_valid_field_path(model_name, clean_path):
                return False
        return True

    def _compile_text_field(self, el, el_type, outer, sty):
        """Compile a text or field element."""
        lines = []
        fs = sty.get("fontSize", 12)
        ff = sty.get("fontFamily", "Helvetica")
        ff_web = self._get_font_family_name(ff)
        ta = sty.get("textAlign", "left")
        va = sty.get("verticalAlign", "middle")
        color = sty.get("color", "#000000")
        bg = sty.get("backgroundColor", "transparent")
        lh = sty.get("lineHeight", 1.2)
        bold = sty.get("bold", False)
        italic = sty.get("italic", False)
        underline = sty.get("underline", False)

        valign = "top" if va == "top" else ("bottom" if va == "bottom" else "middle")

        # Font styling — fontSize in pt to match designer canvas
        font_css = f"font-size: {fs}pt; font-family: &#39;{ff_web}&#39; !important; color: {color}; background-color: {bg}; line-height: {lh};"
        if bold:
            font_css += " font-weight: bold;"
        if italic:
            font_css += " font-style: italic;"
        if underline:
            font_css += " text-decoration: underline;"

        outer.append(font_css)
        css = "; ".join(outer)
        inner = f"display: table-cell; vertical-align: {valign}; text-align: {ta}; width: 100%; height: 100%; padding: 0; margin: 0; border: none; background: transparent; {font_css}"

        lines.append(f'        <div style="{css};">')

        el_h = el.get("height", 12)
        lines.append(
            f'          <div style="display: table; table-layout: fixed; width: 100%; height: {el_h}pt; padding: 0; margin: 0; border: none; background: transparent; {font_css}">'
        )
        if el_type == "field":
            field_expr = el.get("content", "").strip()
            if field_expr.startswith("{{") and field_expr.endswith("}}"):
                field_expr = field_expr[2:-2].strip()

            if not field_expr or field_expr == "field_name":
                lines.append(
                    f'            <div style="{inner}"><span class="text-muted">[Select Field]</span></div>'
                )
            elif field_expr in ("page_number", "total_pages", "page_count"):
                if field_expr == "page_number":
                    lines.append(
                        f'            <div style="{inner}"><span class="page_number_display">&#160;</span></div>'
                    )
                else:
                    try:
                        import json

                        tpl_data = json.loads(self.template_json or "{}")
                        total_pages_count = len(tpl_data.get("pages", [])) or 1
                        _logger.info(
                            "Resolved total_pages_count=%s for template ID %s",
                            total_pages_count,
                            self.id,
                        )
                    except Exception as e:
                        _logger.info(
                            "Error parsing template_json for total_pages_count: %s", e
                        )
                        total_pages_count = 1
                    lines.append(
                        f'            <div style="{inner}"><span class="page_count_display">{total_pages_count}</span></div>'
                    )
            elif field_expr in (
                "current_date",
                "current_time",
                "current_datetime",
                "base_url",
            ):
                BUILTIN_VARS = {
                    "current_date": "datetime.date.today().strftime('%Y-%m-%d')",
                    "current_time": "datetime.datetime.now().strftime('%H:%M:%S')",
                    "current_datetime": "datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')",
                    "base_url": "doc.get_base_url() if doc else ''",
                }
                lines.append(
                    f'            <div style="{inner}"><span t-out="{BUILTIN_VARS[field_expr]}"/></div>'
                )
            elif not self._is_expression_valid(self.model_name, field_expr):
                lines.append(
                    f'            <div style="{inner}"><span>{self._esc_expr(field_expr)}</span></div>'
                )
            else:
                import re

                if re.match(
                    r"^[a-zA-Z_][a-zA-Z0-9_.]*$", field_expr
                ) and not field_expr.startswith("doc."):
                    lines.append(
                        f'            <div style="{inner}"><span t-out="doc.{self._esc_expr(field_expr)}"/></div>'
                    )
                else:
                    lines.append(
                        f'            <div style="{inner}"><span t-out="{self._esc_expr(field_expr)}"/></div>'
                    )
        else:
            text = el.get("content", "")
            processed_text = self._process_text_expressions(text)
            lines.append(f'            <div style="{inner}">{processed_text}</div>')

        lines.append("          </div>")
        lines.append("        </div>")
        return lines

    def _process_text_expressions(self, content):
        """Replace {{expr}} placeholders with QWeb t-out directives."""
        import re

        def replacer(match):
            expr = match.group(1).strip()
            if expr == "page_number":
                return '<span class="page_number_display">&#160;</span>'
            elif expr in ("total_pages", "page_count"):
                try:
                    import json

                    tpl_data = json.loads(self.template_json or "{}")
                    total_pages_count = len(tpl_data.get("pages", [])) or 1
                    _logger.info(
                        "Resolved total_pages_count=%s for template ID %s in text expression",
                        total_pages_count,
                        self.id,
                    )
                except Exception as e:
                    _logger.info(
                        "Error parsing template_json for total_pages_count in text expression: %s",
                        e,
                    )
                    total_pages_count = 1
                return f'<span class="page_count_display">{total_pages_count}</span>'
            elif expr == "current_date":
                return "<t t-out=\"datetime.date.today().strftime('%Y-%m-%d')\"/>"
            elif expr == "current_time":
                return "<t t-out=\"datetime.datetime.now().strftime('%H:%M:%S')\"/>"
            elif expr == "current_datetime":
                return "<t t-out=\"datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')\"/>"
            elif expr == "base_url":
                return "<t t-out=\"doc.get_base_url() if doc else ''\"/>"
            import re

            expr_escaped = self._esc_expr(expr)
            if re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", expr) and not expr.startswith(
                "doc."
            ):
                return f'<t t-out="doc.{expr_escaped}"/>'
            return f'<t t-out="{expr_escaped}"/>'

        return re.sub(r"\{\{([^}]+)\}\}", replacer, content)

    def _compile_image(self, el, outer, sty):
        """Compile an image element using image_data_uri() for inline base64 embedding.

        This is how Odoo's own reports render images in PDFs — it embeds the
        binary data directly as a data URI, avoiding network requests from
        wkhtmltopdf that would fail with ProtocolUnknownError.
        """
        lines = []
        obj_fit = sty.get("objectFit", "contain")
        bg = sty.get("backgroundColor", "")
        bw = sty.get("borderWidth", 0)
        bc = sty.get("borderColor", "#ced4da")
        br = sty.get("borderRadius", 0)

        if bg:
            outer.append(f"background-color: {bg}")
        if bw:
            outer.append(f"border: {bw}pt solid {bc}")
        if br:
            outer.append(f"border-radius: {br}pt")
        outer.append("overflow: hidden")

        css = "; ".join(outer)
        img_style = f"max-width: 100%; max-height: 100%; object-fit: {obj_fit}; display: block; margin: auto;"
        img_mode = el.get("imageSourceMode", "resource")

        if img_mode == "expression" and el.get("expression"):
            field_name = el.get("expression")
            lines.append(
                f'        <t t-set="_img_val" t-value="doc.{self._esc_expr(field_name)}"/>'
            )
            lines.append(f'        <t t-if="_img_val">')
            lines.append(f'          <div style="{css};">')
            lines.append(f'            <t t-if="isinstance(_img_val, bytes)">')
            lines.append(
                f'              <img t-att-src="image_data_uri(_img_val)" style="{img_style}" alt=""/>'
            )
            lines.append(f"            </t>")
            lines.append(f'            <t t-else="">')
            lines.append(
                f'              <span class="text-danger" style="font-size: 10pt; padding: 4pt; display: block;">Invalid Image Field</span>'
            )
            lines.append(f"            </t>")
            lines.append(f"          </div>")
            lines.append(f"        </t>")

        elif img_mode == "resource" and el.get("resourceId"):
            res_id = int(el.get("resourceId"))
            # Access the resource record and call get_image_uri to get the correct base64 data URI
            lines.append(f'          <div style="{css};">')
            lines.append(
                f'            <t t-set="_res_rec" t-value="doc.env[\'report.designer.resource\'].browse({res_id})"/>'
            )
            lines.append(
                f'            <t t-set="_res_uri" t-value="_res_rec.get_image_uri()"/>'
            )
            lines.append(
                f'            <img t-if="_res_uri" t-att-src="_res_uri" style="{img_style}" alt=""/>'
            )
            lines.append(f"          </div>")
        else:
            lines.append(f'          <div style="{css};">')
            lines.append(
                f'            <div style="width: 100%; height: 100%; background: #eee;"/>'
            )
            lines.append(f"          </div>")

        return lines

    def _hex_to_rgba(self, hex_str, opacity):
        """Convert a hex color string to rgba format with the given opacity."""
        if not hex_str or not isinstance(hex_str, str):
            return hex_str
        hex_clean = hex_str.lstrip("#")
        try:
            if len(hex_clean) == 3:
                r = int(hex_clean[0] * 2, 16)
                g = int(hex_clean[1] * 2, 16)
                b = int(hex_clean[2] * 2, 16)
            elif len(hex_clean) == 6:
                r = int(hex_clean[0:2], 16)
                g = int(hex_clean[2:4], 16)
                b = int(hex_clean[4:6], 16)
            else:
                return hex_str
            return f"rgba({r}, {g}, {b}, {opacity})"
        except Exception:
            return hex_str

    def _compile_watermark(self, el, outer, sty):
        """Compile a watermark element.

        We must separate opacity and transform into different DOM nodes, otherwise WKHTMLTOPDF ignores the rotation.
        We must also use table-layout: fixed, otherwise rotated contents can cause infinite width calculations leading to blank pages.
        """
        lines = []
        mode = el.get("watermarkMode", "text")

        color = sty.get("color", "#6B7280")
        opacity = sty.get("opacity", 0.18)

        # Use the raw font size value as pt to perfectly match _compile_text_field behavior
        fs_pt = sty.get("fontSize", 64)

        # Use el_rot (bounding box rotation) instead of Appearance rotation
        # because we removed Appearance rotation from the UI so it behaves like Text/Image.
        rotation = el.get("rotation")
        if rotation is None:
            rotation = sty.get("rotation", 0)

        font_family = sty.get("fontFamily", "Helvetica")
        ff_web = self._get_font_family_name(font_family)

        # Outer gets opacity, position, and bounding box. NO TRANSFORM!
        outer.append(f"opacity: {opacity}; pointer-events: none;")
        outer_css = "; ".join(outer)

        el_h = el.get("height", 30)
        lines.append(f'        <div style="{outer_css}">')
        lines.append(
            f'          <div style="display: table; table-layout: fixed; width: 100%; height: {el_h}pt; padding: 0; margin: 0; border: none; background: transparent;">'
        )
        lines.append(
            '            <div style="display: table-cell; vertical-align: middle; text-align: center; width: 100%; height: 100%; padding: 0; margin: 0; border: none; background: transparent;">'
        )

        # Inner gets the rotation!
        rotate_css = f"display: inline-block; transform: rotate({rotation}deg); -webkit-transform: rotate({rotation}deg);"

        if mode == "text":
            content = el.get("content", "DRAFT")
            if not content:
                content = "DRAFT"
            processed = self._process_text_expressions(content)

            rgba_color = self._hex_to_rgba(color, opacity)
            text_css = f"color: {rgba_color}; font-family: &#39;{ff_web}&#39; !important; font-size: {fs_pt}pt; font-weight: bold; white-space: nowrap;"
            lines.append(
                f'              <div style="{rotate_css} {text_css}">{processed}</div>'
            )

        elif mode == "image":
            img_mode = el.get("imageSourceMode", "resource")
            img_style = f"max-width: 100%; max-height: 100%; object-fit: contain; opacity: {opacity};"

            if img_mode == "expression" and el.get("expression"):
                field_name = el.get("expression")
                lines.append(
                    f'              <t t-set="_img_val" t-value="doc.{self._esc_expr(field_name)}"/>'
                )
                lines.append(f'              <t t-if="_img_val">')
                lines.append(f'                <div style="{rotate_css}">')
                lines.append(
                    f'                  <t t-if="isinstance(_img_val, bytes)">'
                )
                lines.append(
                    f'                    <img t-att-src="image_data_uri(_img_val)" style="{img_style}" alt=""/>'
                )
                lines.append(f"                  </t>")
                lines.append(f"                </div>")
                lines.append(f"              </t>")
            elif img_mode == "resource" and el.get("resourceId"):
                res_id = int(el.get("resourceId"))
                lines.append(f'              <div style="{rotate_css}">')
                lines.append(
                    f'                <t t-set="_res_rec" t-value="doc.env[\'report.designer.resource\'].browse({res_id})"/>'
                )
                lines.append(
                    f'                <t t-set="_res_uri" t-value="_res_rec.get_image_uri()"/>'
                )
                lines.append(
                    f'                <img t-if="_res_uri" t-att-src="_res_uri" style="{img_style}" alt=""/>'
                )
                lines.append(f"              </div>")

        lines.append("            </div>")
        lines.append("          </div>")
        lines.append("        </div>")
        return lines

    def _compile_barcode(self, el, outer, sty, barcode_type="Code128"):
        """Compile a barcode or qrcode element."""
        lines = []
        css = "; ".join(outer)
        # Flex column allows putting text on top or bottom seamlessly
        flex_css = f"{css}; display: flex; flex-direction: column; align-items: center; justify-content: center; overflow: hidden;"

        content = el.get("content", "")
        if not content:
            content = el.get("type", "barcode")

        show_text = el.get("showBarcodeText", True)
        pos = el.get("barcodeTextPosition", "Bottom")

        if barcode_type == "QR":
            try:
                w = float(el.get("width", 100))
                h = float(el.get("height", 100))
            except (ValueError, TypeError):
                w = 100.0
                h = 100.0
            if show_text:
                h = max(10.0, h - 14.0)
            size = min(w, h)
            img_style = (
                f"width: {size}pt; height: {size}pt; display: block; margin: 0 auto;"
            )
            size_px = int(size * 1.33)
            url_params = f"&amp;width={size_px}&amp;height={size_px}"
        else:
            img_style = "max-width: 100%; max-height: 100%; display: block; margin: auto; flex: 1;"
            url_params = ""

        is_expr = content.startswith("{{") and content.endswith("}}")

        if is_expr:
            expr = content[2:-2].strip()
            expr_esc = self._esc_expr(expr)
            text_span = f'<div style="text-align: center; font-size: 10pt; width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"><t t-esc="{expr_esc}"/></div>'
            img_tag = f'<img t-if="{expr_esc}" t-attf-src="/report/barcode/?barcode_type={barcode_type}&amp;value={{{{ {expr_esc} }}}}&amp;humanreadable=0{url_params}" style="{img_style}" alt="Barcode"/>'
        else:
            text_span = f'<div style="text-align: center; font-size: 10pt; width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{content}</div>'
            img_tag = f'<img src="/report/barcode/?barcode_type={barcode_type}&amp;value={content}&amp;humanreadable=0{url_params}" style="{img_style}" alt="Barcode"/>'

        lines.append(f'        <div style="{flex_css}">')
        if show_text and pos == "Top":
            lines.append(f"          {text_span}")
        lines.append(f"          {img_tag}")
        if show_text and pos == "Bottom":
            lines.append(f"          {text_span}")
        lines.append(f"        </div>")

        return lines

    def _compile_line(self, el, outer, sty, el_h):
        """Compile a line element."""
        lines = []
        color = sty.get("color", "#000000")
        bw = sty.get("borderWidth", 1)
        bs = sty.get("borderStyle", "solid")
        margin_t = (el_h - bw) / 2
        outer.append(f"border-top: {bw}pt {bs} {color}")
        outer.append(f"margin-top: {margin_t}pt")
        css = "; ".join(outer)
        lines.append(f'        <div style="{css}"></div>')
        return lines

    def _compile_shape(self, el, outer, sty):
        """Compile a shape/rectangle element."""
        lines = []
        shape_type = el.get("shapeType") or el.get("type", "rectangle")
        fill = sty.get("fillColor") or "transparent"
        fill_opacity = sty.get("fillOpacity", 1.0)
        stroke = sty.get("strokeColor") or "#000000"
        stroke_w = sty.get("strokeWidth", 1)
        stroke_style = sty.get("strokeStyle") or "solid"
        dash = (
            "5,5"
            if stroke_style == "dashed"
            else ("2,2" if stroke_style == "dotted" else "none")
        )

        css = "; ".join(outer)
        lines.append(f'        <div style="{css}">')
        lines.append(
            f'          <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none" style="overflow: visible; display: block;">'
        )

        common = f'fill="{fill}" fill-opacity="{fill_opacity}" stroke="{stroke}" stroke-width="{stroke_w}" stroke-dasharray="{dash}" vector-effect="non-scaling-stroke"'
        if shape_type == "rectangle":
            rx = sty.get("cornerRadius", 0)
            lines.append(
                f'            <rect x="0" y="0" width="100" height="100" rx="{rx}" ry="{rx}" {common}/>'
            )
        elif shape_type == "ellipse":
            lines.append(
                f'            <ellipse cx="50" cy="50" rx="50" ry="50" {common}/>'
            )
        elif shape_type == "triangle":
            lines.append(f'            <polygon points="50,0 100,100 0,100" {common}/>')
        elif shape_type == "diamond":
            lines.append(
                f'            <polygon points="50,0 100,50 50,100 0,50" {common}/>'
            )
        elif shape_type == "polygon":
            lines.append(
                f'            <polygon points="50,0 95,25 95,75 50,100 5,75 5,25" {common}/>'
            )
        elif shape_type == "star":
            lines.append(
                f'            <polygon points="50,0 63,38 100,38 69,59 82,100 50,75 18,100 31,59 0,38 37,38" {common}/>'
            )

        lines.append(f"          </svg>")
        lines.append("        </div>")
        return lines

    def _compile_table(self, el, outer, sty):
        """Compile a table element."""
        lines = []
        data_source = el.get("dataSource", "")
        columns = el.get("content", [])
        if not isinstance(columns, list):
            columns = []

        show_header = el.get("showHeader", True)
        tbl_header_height = el.get("headerHeight", 24)
        show_footer = el.get("showFooter", False)
        repeat_new_page = el.get("repeatNewPage", True)

        css = "; ".join(outer)
        tbl_css = "width: 100%; border-collapse: collapse; border: 1pt solid #ced4da; table-layout: fixed; word-wrap: break-word; overflow-wrap: break-word;"

        lines.append(f'        <div style="{css};">')
        lines.append(f'          <table style="{tbl_css}">')

        if show_header:
            thead_style = "" if repeat_new_page else "page-break-inside: avoid;"
            lines.append(f'            <thead style="{thead_style}">')
            lines.append(
                f'              <tr style="border-bottom: 1pt solid #ced4da; background-color: #f8f9fa; height: {tbl_header_height}pt;">'
            )
            for col in columns:
                col_w = col.get("widthValue", 50)
                col_w_type = col.get("widthType", "percent")
                unit = "%" if col_w_type == "percent" else "pt"
                th_css = f"width: {col_w}{unit}; text-align: left; padding: 4pt; border-right: 1pt solid #ced4da; font-size: 11pt; font-weight: bold; vertical-align: middle;"
                lines.append(
                    f'                <th style="{th_css}">{col.get("header", "")}</th>'
                )
            lines.append("              </tr>")
            lines.append("            </thead>")

        lines.append("            <tbody>")
        if data_source:
            loop_expr = el.get("loopExpression", "doc.order_line")
            if not loop_expr:
                loop_expr = "doc.order_line"
            lines.append(
                f'              <t t-foreach="{self._esc_expr(loop_expr)}" t-as="row">'
            )
            lines.append(
                '                <tr style="border-bottom: 1pt solid #dee2e6;">'
            )
            for col in columns:
                col_w = col.get("widthValue", 50)
                col_w_type = col.get("widthType", "percent")
                unit = "%" if col_w_type == "percent" else "pt"
                td_css = f"width: {col_w}{unit}; padding: 4pt; border-right: 1pt solid #ced4da; font-size: 11pt; vertical-align: middle;"
                lines.append(f'                  <td style="{td_css}">')

                c_type = col.get("contentType", "text")
                c_expr = col.get("contentExpression", "").strip()
                if c_expr.startswith("{{") and c_expr.endswith("}}"):
                    c_expr = c_expr[2:-2].strip()

                if not c_expr or c_expr == "field_name":
                    lines.append(
                        '                    <span class="text-muted">[Select Field]</span>'
                    )
                else:
                    row_model = self.model_name
                    loop_expr = el.get("loopExpression", "") or "doc.order_line"
                    if loop_expr.startswith("doc."):
                        loop_path = loop_expr[4:]
                        try:
                            parts = loop_path.split(".")
                            curr = self.env[self.model_name]
                            for p in parts:
                                f = curr._fields[p]
                                if f.relational:
                                    curr = self.env[f.comodel_name]
                            row_model = curr._name
                        except Exception:
                            pass

                    val_expr = c_expr
                    if val_expr.startswith("doc."):
                        val_expr = val_expr[4:]
                    elif val_expr.startswith("row."):
                        val_expr = val_expr[4:]

                    if c_expr:
                        clean_expr = (
                            c_expr.replace("doc.", "row.", 1)
                            if c_expr.startswith("doc.")
                            else f"row.{c_expr}"
                        )
                    else:
                        clean_expr = ""
                    clean_expr_esc = self._esc_expr(clean_expr)

                    is_valid = self._is_expression_valid(row_model, val_expr)

                    if not is_valid:
                        lines.append(
                            f"                    <span>{clean_expr_esc}</span>"
                        )
                    elif c_type == "image":
                        if clean_expr_esc:
                            lines.append(
                                f'                    <t t-set="_img_val" t-value="{clean_expr_esc}"/>'
                            )
                            lines.append(f'                    <t t-if="_img_val">')
                            lines.append(
                                f'                      <t t-if="isinstance(_img_val, bytes)">'
                            )
                            lines.append(
                                f'                        <img t-att-src="image_data_uri(_img_val)" style="max-width: 100%; max-height: 48pt; display: block; margin: auto;" alt=""/>'
                            )
                            lines.append(f"                      </t>")
                            lines.append(f'                      <t t-else="">')
                            lines.append(
                                f'                        <span class="text-danger" style="font-size: 8pt;">Invalid Image</span>'
                            )
                            lines.append(f"                      </t>")
                            lines.append(f"                    </t>")
                    elif c_type == "barcode":
                        if clean_expr_esc:
                            lines.append(
                                f'                    <div t-if="{clean_expr_esc}" style="text-align: center;">'
                            )
                            lines.append(
                                f'                      <img t-attf-src="/report/barcode/?barcode_type=Code128&amp;value={{{{ {clean_expr_esc} }}}}" style="width: 100%; height: 30pt;"/>'
                            )
                            lines.append(f"                    </div>")
                    else:
                        if clean_expr_esc:
                            lines.append(
                                f'                    <span t-out="{clean_expr_esc}"/>'
                            )
                lines.append("                  </td>")
            lines.append("                </tr>")
            lines.append("              </t>")
        else:
            lines.append(
                '                <tr style="border-bottom: 1pt solid #dee2e6;">'
            )
            for col in columns:
                col_w = col.get("widthValue", 50)
                col_w_type = col.get("widthType", "percent")
                unit = "%" if col_w_type == "percent" else "pt"
                td_css = f"width: {col_w}{unit}; padding: 4pt; border-right: 1pt solid #ced4da; font-size: 11pt;"
                lines.append(f'                  <td style="{td_css}">(empty)</td>')
            lines.append("                </tr>")
        lines.append("            </tbody>")

        if show_footer:
            lines.append("            <tfoot>")
            lines.append(
                '              <tr style="border-top: 1pt solid #ced4da; background-color: #f8f9fa;">'
            )
            for col in columns:
                col_w = col.get("widthValue", 50)
                col_w_type = col.get("widthType", "percent")
                unit = "%" if col_w_type == "percent" else "pt"
                td_css = f"width: {col_w}{unit}; padding: 4pt; border-right: 1pt solid #ced4da; font-size: 11pt; font-weight: bold;"
                lines.append(
                    f'                <td style="{td_css}">{col.get("footer", "")}</td>'
                )
            lines.append("              </tr>")
            lines.append("            </tfoot>")

        lines.append("          </table>")
        lines.append("        </div>")
        return lines

    # -------------------------------------------------------------------------
    # Main compile entry point
    # -------------------------------------------------------------------------

    def compile_qweb_arch(self):
        self.ensure_one()
        try:
            data = json.loads(self.template_json or "{}")
        except Exception:
            data = {}

        pages = data.get("pages", [])

        # Page dimensions — SAME units as the designer canvas (px at 72dpi).
        # The designer stores pageWidth = round(paper_width_mm * 2.83465).
        # We use these exact values so all element coordinates map 1:1.
        width = int(round(self.paper_width * 2.83465))
        height = int(round(self.paper_height * 2.83465))

        margin_top = float(self.margin_top * 2.83465)
        margin_bottom = float(self.margin_bottom * 2.83465)
        margin_left = float(self.margin_left * 2.83465)
        margin_right = float(self.margin_right * 2.83465)

        printable_width = width - margin_left - margin_right
        printable_height = height - margin_top - margin_bottom

        xml = []
        xml.append('<?xml version="1.0"?>')
        xml.append(
            f'<t t-name="cr_dynamic_report_studio.report_designer_template_{self.id}">'
        )
        xml.append("  <main>")
        xml.append('    <t t-foreach="docs" t-as="doc">')

        xml.append('    <div class="article" style="position: relative; width: 100%;">')
        xml.append("      <style>")
        xml.append("        html, body, .article, .container, .o_body_pdf {")
        xml.append("          margin: 0 !important;")
        xml.append("          padding: 0 !important;")
        xml.append("          width: 100% !important;")
        xml.append("          max-width: 100% !important;")
        xml.append("          background: transparent;")
        xml.append("        }")
        xml.append("        * { box-sizing: border-box; }")
        xml.append("        body { counter-reset: page_counter; }")
        xml.append(
            "        .o_designer_report_page { counter-increment: page_counter; }"
        )
        xml.append(
            "        .page_number_display::after { content: counter(page_counter); }"
        )
        xml.append("        @font-face {")
        xml.append("          font-family: 'Helvetica';")
        xml.append(
            "          src: url('/cr_dynamic_report_studio/static/src/fonts/arial.ttf') format('truetype');"
        )
        xml.append("        }")
        xml.append("        @font-face {")
        xml.append("          font-family: 'Arial';")
        xml.append(
            "          src: url('/cr_dynamic_report_studio/static/src/fonts/arial.ttf') format('truetype');"
        )
        xml.append("        }")
        xml.append("        @font-face {")
        xml.append("          font-family: 'Times New Roman';")
        xml.append(
            "          src: url('/cr_dynamic_report_studio/static/src/fonts/times.ttf') format('truetype');"
        )
        xml.append("        }")
        xml.append("        @font-face {")
        xml.append("          font-family: 'Courier New';")
        xml.append(
            "          src: url('/cr_dynamic_report_studio/static/src/fonts/cour.ttf') format('truetype');"
        )
        xml.append("        }")
        xml.append("        @font-face {")
        xml.append("          font-family: 'Verdana';")
        xml.append(
            "          src: url('/cr_dynamic_report_studio/static/src/fonts/verdana.ttf') format('truetype');"
        )
        xml.append("        }")
        xml.append("        @font-face {")
        xml.append("          font-family: 'Georgia';")
        xml.append(
            "          src: url('/cr_dynamic_report_studio/static/src/fonts/georgia.ttf') format('truetype');"
        )
        xml.append("        }")
        xml.append("      </style>")

        seg_idx = 0

        for p_idx, page in enumerate(pages):
            body_els = page.get("elements", [])

            # Split body by pagebreaks
            pagebreaks = sorted(
                [e for e in body_els if e.get("type") == "pagebreak"],
                key=lambda e: e.get("y", 0),
            )

            segments = []
            last_y = 0
            for pb in pagebreaks:
                pb_y = pb.get("y", 0)
                segments.append(
                    {
                        "offset_y": last_y,
                        "els": [
                            e
                            for e in body_els
                            if e.get("type") != "pagebreak"
                            and last_y <= e.get("y", 0) < pb_y
                        ],
                        "is_last": False,
                    }
                )
                last_y = pb_y
            segments.append(
                {
                    "offset_y": last_y,
                    "els": [
                        e
                        for e in body_els
                        if e.get("type") != "pagebreak" and e.get("y", 0) >= last_y
                    ],
                    "is_last": True,
                }
            )

            for seg in segments:
                # Use page-break-before: always for all segments except the first one
                is_first = p_idx == 0 and seg == segments[0]
                pbb = "avoid" if is_first else "always"

                page_css = (
                    f"position: relative; "
                    f"width: {self.paper_width}mm; "
                    f"height: {self.paper_height - 0.5}mm; "
                    f"max-height: {self.paper_height - 0.5}mm; "
                    f"margin: 0; padding: 0; "
                    f"background-color: transparent; "
                    f"page-break-before: {pbb}; "
                    f"overflow: hidden;"
                )
                xml.append(
                    f'      <div class="o_designer_report_page" style="{page_css}">'
                )

                header_enabled = data.get("headerEnabled", False)
                header_height = data.get("headerHeight", 50)
                footer_enabled = data.get("footerEnabled", False)
                footer_height = data.get("footerHeight", 50)

                # Inject watermarks from all pages, AND global headers/footers from Page 0 into each page
                for idx, w_page in enumerate(pages):
                    w_els = w_page.get("elements", [])
                    for el in w_els:
                        el_type = el.get("type")
                        el_y = el.get("y", 0)

                        is_watermark = el_type == "watermark"
                        is_global_header = (
                            idx == 0
                            and header_enabled
                            and el_y < header_height
                            and el_type != "watermark"
                        )
                        is_global_footer = (
                            idx == 0
                            and footer_enabled
                            and el_y >= (height - footer_height)
                            and el_type != "watermark"
                        )

                        if is_watermark or is_global_header or is_global_footer:
                            try:
                                z_idx = w_els.index(el)
                            except ValueError:
                                z_idx = 0
                            xml.extend(self._compile_element(el, 0, z_index=z_idx))

                # Render body elements with flow blocks to handle dynamic tables
                # Exclude watermarks and global headers/footers since they were handled globally above
                seg_body_els = []
                for e in seg["els"]:
                    e_type = e.get("type")
                    e_y = e.get("y", 0)

                    if e_type == "watermark":
                        continue

                    # If this is Page 0, exclude elements that fall into the global header/footer bands
                    if p_idx == 0:
                        if header_enabled and e_y < header_height:
                            continue
                        if footer_enabled and e_y >= (height - footer_height):
                            continue

                    seg_body_els.append(e)

                seg_body_els = sorted(seg_body_els, key=lambda e: e.get("y", 0))

                # Grouping Logic
                # Separate tables and absolute elements
                tables = sorted(
                    [e for e in seg_body_els if e.get("type") == "table"],
                    key=lambda e: e.get("y", 0),
                )
                remaining_abs = [e for e in seg_body_els if e.get("type") != "table"]

                flow_blocks = []
                for t in tables:
                    t_y = t.get("y", 0)
                    t_bottom = t_y + t.get("height", 100)

                    # Gather absolute elements that start above the table's bottom
                    abs_before = []
                    for el in list(remaining_abs):
                        if el.get("y", 0) < t_bottom:
                            abs_before.append(el)
                            remaining_abs.remove(el)

                    if abs_before:
                        flow_blocks.append({"type": "abs", "els": abs_before})

                    flow_blocks.append({"type": "table", "el": t})

                # Any remaining absolute elements go after all tables
                if remaining_abs:
                    flow_blocks.append({"type": "abs", "els": remaining_abs})

                if seg_body_els:
                    content_top = float(margin_top)
                    if header_enabled:
                        content_top = max(content_top, float(header_height))

                    content_bottom = float(height - margin_bottom)
                    if footer_enabled:
                        content_bottom = min(
                            content_bottom, float(height - footer_height)
                        )

                    content_left = float(margin_left)
                    content_width = float(width - margin_left - margin_right)
                    content_height = float(content_bottom - content_top)

                    xml.append(
                        f'        <div style="position: absolute; left: {content_left}pt; top: {content_top}pt; width: {content_width}pt; height: {content_height}pt; overflow: hidden; margin: 0; padding: 0; z-index: 2;">'
                    )

                    flow_y_offset = 0
                    for block in flow_blocks:
                        if block["type"] == "abs":
                            if flow_y_offset > 0:
                                # Calculate the required height of this absolute block
                                max_y = 0
                                for bel in block["els"]:
                                    b_y = bel.get("y", 0)
                                    b_h = bel.get("height", 50)
                                    if (b_y + b_h) > max_y:
                                        max_y = b_y + b_h
                                climb_top = content_top
                                container_height = max_y - flow_y_offset
                                if container_height < 0:
                                    container_height = 0
                                xml.append(
                                    f'        <div style="position: relative; height: {container_height}pt;">'
                                )

                            for bel in block["els"]:
                                try:
                                    z_idx = body_els.index(bel)
                                except ValueError:
                                    z_idx = 0
                                xml.extend(
                                    self._compile_element(
                                        bel,
                                        seg["offset_y"],
                                        margin_top=content_top,
                                        margin_left=content_left,
                                        flow_y_offset=flow_y_offset,
                                        z_index=z_idx,
                                    )
                                )

                            if flow_y_offset > 0:
                                xml.append("        </div>")
                                flow_y_offset += container_height
                        elif block["type"] == "table":
                            t_el = block["el"]
                            t_el_y_raw = t_el.get("y", 0)

                            if flow_y_offset > 0:
                                spacer_height = t_el_y_raw - flow_y_offset
                            else:
                                spacer_height = t_el_y_raw - seg["offset_y"]

                            if spacer_height > 0:
                                xml.append(
                                    f'        <div style="height: {spacer_height}pt; width: 100%;"></div>'
                                )

                            try:
                                z_idx = body_els.index(t_el)
                            except ValueError:
                                z_idx = 0
                            xml.extend(
                                self._compile_element(
                                    t_el,
                                    seg["offset_y"],
                                    margin_top=content_top,
                                    margin_left=content_left,
                                    flow_y_offset=flow_y_offset,
                                    z_index=z_idx,
                                )
                            )
                            flow_y_offset = t_el_y_raw + t_el.get("height", 100)

                    xml.append("        </div>")

                xml.append("      </div>")
                seg_idx += 1

        xml.append("    </div>")
        xml.append("  </t>")
        xml.append("  </main>")
        xml.append("</t>")

        return "\n".join(xml)

    def _should_print_band(self, enabled, print_on, seg_idx, total_segments):
        """Check whether a header/footer band should print on this segment."""
        if not enabled:
            return False
        if print_on == "all":
            return True
        if print_on == "first" and seg_idx == 0:
            return True
        if print_on == "last" and seg_idx == total_segments - 1:
            return True
        if print_on == "even" and (seg_idx + 1) % 2 == 0:
            return True
        return False

    def create_or_update_qweb_view(self):
        self.ensure_one()
        arch = self.compile_qweb_arch()
        view_key = f"cr_dynamic_report_studio.report_designer_template_{self.id}"
        view = self.env["ir.ui.view"].search([("key", "=", view_key)], limit=1)
        if not view:
            view = self.env["ir.ui.view"].search(
                [("key", "=", f"report_designer_template_{self.id}")], limit=1
            )
        if view:
            view.write(
                {
                    "arch": arch,
                    "key": view_key,
                }
            )
        else:
            self.env["ir.ui.view"].create(
                {
                    "name": f"Report Template {self.name} (ID {self.id})",
                    "type": "qweb",
                    "key": view_key,
                    "arch": arch,
                }
            )
        # Invalidate all caches so Odoo picks up the new view immediately
        self.env.registry.clear_all_caches()

    def write(self, vals):
        res = super(ReportDesignerTemplate, self).write(vals)
        trigger_fields = {
            "template_json",
            "paper_width",
            "paper_height",
            "name",
            "margin_top",
            "margin_bottom",
            "margin_left",
            "margin_right",
            "orientation",
        }
        if trigger_fields & set(vals.keys()):
            for record in self:
                view_key = (
                    f"cr_dynamic_report_studio.report_designer_template_{record.id}"
                )
                if record.report_action_id or self.env["ir.ui.view"].search(
                    [("key", "=", view_key)], limit=1
                ):
                    record.create_or_update_qweb_view()
                if record.report_action_id:
                    record._update_paper_format()
        return res

    def action_duplicate(self):
        for rec in self:
            rec.copy({"name": f"{rec.name} (Copy)"})

    def action_export_json(self):
        self.ensure_one()
        import base64

        json_data = self.template_json or "{}"
        attachment = self.env["ir.attachment"].create(
            {
                "name": f"{self.name}_template.json",
                "type": "binary",
                "datas": base64.b64encode(json_data.encode("utf-8")),
                "res_model": "report.designer.template",
                "res_id": self.id,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "new",
        }

    def action_format_json(self):
        for record in self:
            if record.template_json:
                try:
                    parsed = json.loads(record.template_json)
                    record.template_json = json.dumps(parsed, indent=4)
                except ValueError:
                    pass

    @api.model
    def action_validate_expression(self, expression, model_name=None):
        """Validate a Python expression syntax and suggest corrections if needed."""
        if not expression:
            return {"valid": True, "error": "", "suggestion": ""}

        # 1. Check Python syntax compilation
        try:
            compile(expression, "<string>", "eval")
        except SyntaxError as e:
            suggestion = ""
            error_msg = str(e)

            # Common error 1: curly braces instead of dot notation
            if "{" in expression or "}" in expression:
                suggestion = "Did you mean to use dot notation? e.g. doc.partner_id instead of doc{partner_id}"
            # Common error 2: single equals instead of double equals in comparison
            elif (
                "=" in expression
                and "==" not in expression
                and "!=" not in expression
                and "<=" not in expression
                and ">=" not in expression
            ):
                suggestion = "Did you mean to use '==' for comparison?"
            # Common error 3: missing dot prefix for doc
            elif any(
                part in expression for part in ["partner_id", "name", "amount_total"]
            ) and not any(expr in expression for expr in ["doc.", "user.", "object."]):
                suggestion = "Make sure to prefix fields with 'doc.', e.g. doc.name"

            return {
                "valid": False,
                "error": f"Syntax Error: {error_msg}",
                "suggestion": suggestion,
            }

        # 1b. Check for string methods incorrectly used as global functions
        import re

        invalid_fns = [
            "upper",
            "lower",
            "strip",
            "split",
            "replace",
            "find",
            "startswith",
            "endswith",
            "strftime",
            "strptime",
        ]
        for fn in invalid_fns:
            if re.search(r"(?<!\.)\b" + fn + r"\s*\(", expression):
                suggestion = f"'{fn}' is a string method, not a global function. Use dot notation: doc.name.{fn}() instead of {fn}(doc.name)"
                return {
                    "valid": False,
                    "error": f"NameError: global name '{fn}' is not defined in Odoo QWeb environment.",
                    "suggestion": suggestion,
                }

        # 2. Trace and validate fields prefixed with "doc."
        import re

        doc_paths = re.findall(r"\bdoc\.([a-zA-Z0-9_.]+)", expression)
        if doc_paths and model_name:
            try:
                env_model = self.env[model_name]
                for path in doc_paths:
                    parts = path.split(".")
                    current_model = env_model
                    valid_path = []
                    for part in parts:
                        # Skip special helper methods
                        if part in ("filtered", "mapped", "sorted", "filtered_domain"):
                            break
                        if part not in current_model._fields:
                            import difflib

                            matches = difflib.get_close_matches(
                                part, list(current_model._fields.keys()), n=1
                            )
                            suggested_part = matches[0] if matches else None

                            wrong_path = "doc." + ".".join(valid_path + [part])
                            if suggested_part:
                                correct_path = "doc." + ".".join(
                                    valid_path + [suggested_part]
                                )
                                suggestion = f"Field '{part}' does not exist on {current_model._name}. Did you mean '{suggested_part}'? (Full path: {correct_path})"
                            else:
                                suggestion = f"Field '{part}' does not exist on {current_model._name}."

                            return {
                                "valid": False,
                                "error": f"Field '{part}' is not valid on {current_model._name}.",
                                "suggestion": suggestion,
                            }

                        valid_path.append(part)
                        field = current_model._fields[part]
                        if field.relational:
                            current_model = self.env[field.comodel_name]
                        else:
                            break
            except Exception:
                pass

        return {"valid": True, "error": "", "suggestion": ""}
