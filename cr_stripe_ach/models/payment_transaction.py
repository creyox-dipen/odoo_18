# from odoo import models
# import logging
#
# _logger = logging.getLogger(__name__)
#
#
# class PaymentTransaction(models.Model):
#     _inherit = "payment.transaction"
#
#     def _handle_notification_data(self, provider, data):
#         """Extend webhook handling to auto-post payment on success"""
#         res = super()._handle_notification_data(provider, data)
#         _logger.info("payment transaction created😊😊😊😊")
#         if provider == 'stripe' and data.get('event_type') == 'payment_intent.succeeded':
#             # Ensure we are working on a real transaction
#             invoice = self.invoice_ids
#             _logger.info("➡️➡️➡️➡️", invoice)
#             _logger.info(invoice.payment_ids)
#             for payment in invoice.payment_ids:
#                 payment.action_validate()
#
#         return res
