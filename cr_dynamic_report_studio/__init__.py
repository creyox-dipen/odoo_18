# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from . import models

try:
    import PyPDF2

    # Monkey-patch PyPDF2 to prevent Odoo server crash on PyPDF2 3.0.0+
    if hasattr(PyPDF2, "PdfReader") and not hasattr(PyPDF2.PdfReader, "numPages"):
        PyPDF2.PdfReader.numPages = property(lambda self: len(self.pages))
except (ImportError, AttributeError):
    pass
