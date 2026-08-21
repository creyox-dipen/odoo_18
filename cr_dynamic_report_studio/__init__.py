# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
from . import models

try:
    import PyPDF2
    if hasattr(PyPDF2, 'PdfReader') and not hasattr(PyPDF2.PdfReader, 'numPages'):
        PyPDF2.PdfReader.numPages = property(lambda self: len(self.pages))
    elif hasattr(PyPDF2, 'PdfFileReader') and not hasattr(PyPDF2.PdfFileReader, 'numPages'):
        PyPDF2.PdfFileReader.numPages = property(lambda self: len(self.pages))
except Exception:
    pass



