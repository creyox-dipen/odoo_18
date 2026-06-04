# -*- coding: utf-8 -*-
# Part of Creyox Technologies

# ------------------------------------------------------------------
# Patch Odoo's HTML sanitizer to preserve our diagram XML attribute.
#
# Odoo's html_sanitize() in odoo/tools/mail.py uses an explicit
# allowlist (safe_attrs) of data-* attributes. Any attribute NOT in
# that list is stripped when sanitize_attributes=True.
#
# We add 'data-drawio-xml' so the diagram's Draw.io XML survives
# when an HTML field (e.g. Sale Order notes) is saved to the DB.
# ------------------------------------------------------------------
from odoo.tools import mail as _mail

_mail.safe_attrs = _mail.safe_attrs | frozenset(["data-drawio-xml"])
