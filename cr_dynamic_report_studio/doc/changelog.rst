18.0.0.0(Date: 14th Aug,2026)
-------------------------------
- Initial release

18.0.0.1 (Date: 1st Sep, 2026)
-------------------------------
- [Fix] Resolved resource image rendering issues under bin_size context.
- [Fix] Added support for converting and rendering .ico icon format.
- [Fix] Resolved watermark rendering and alignment issues in PDF previews by implementing viewport-safe coordinates, margin offset compensation, and native vertical table-cell centering.
- [Fix] Fixed custom and system font family rendering under sandboxed wkhtmltopdf environments by embedding standard fonts over HTTP.
- [Fix] Dynamically map and compile element z-index values to preserve studio-designed stacking order in report previews.
- [Fix] Fixed vertical alignment collapsing in PDF previews by defining absolute height on table wrappers.
- [Fix] Fixed selected record text visibility inside the preview dialog box when Odoo is in dark mode.
- [Fix] Fixed field and text components not rendering built-in system variables (like current_date, page_number, page_count, base_url) dynamically in PDF previews by using datetime/CSS counters/record ORM.