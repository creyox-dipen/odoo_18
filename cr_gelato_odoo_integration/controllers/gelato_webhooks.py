# -*- coding: utf-8 -*-
# Part of Creyox Technologies
import logging
from odoo import _
from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)


class GelatoWebhookkController(Controller):
    _webhook_url = '/gelato/webhook'

    @route(_webhook_url, type='http', methods=['POST'], auth='public', csrf=False)
    def webhook_details_from_gelato(self):
        data_info = request.get_json_data()
        x = data_info['event']

        if data_info['event'] == 'order_status_updated':
            sale_order_id = int(data_info['orderReferenceId'])
            is_sale_order_id_exist = request.env['sale.order'].sudo().browse(sale_order_id).exists()
            if is_sale_order_id_exist:
                sale = request.env['sale.order'].sudo().search([('id', '=', sale_order_id)])
                received_signature = request.httprequest.headers.get('signature', '')
                is_correct = self.is_notification_from_Correct_webhook(sale, received_signature)
                if is_correct:
                    self.order_status_event(sale, data_info)

        if data_info['event'] == 'order_item_status_updated':
            sale_order_id = int(data_info['orderReferenceId'])
            is_sale_order_id_exist = request.env['sale.order'].sudo().browse(sale_order_id).exists()
            if is_sale_order_id_exist:
                sale = request.env['sale.order'].sudo().search([('id', '=', sale_order_id)])
                received_signature = request.httprequest.headers.get('signature', '')
                is_correct = self.is_notification_from_Correct_webhook(sale, received_signature)
                if is_correct:
                    self.order_status_event(sale, data_info)

        if data_info['event'] == 'store_product_template_updated':
            storeProductTemplateId = data_info['storeProductTemplateId']
            is_storeProductTemplateId_exist = request.env['product.template'].sudo().search(
                [('cr_template_ref', '=', storeProductTemplateId)]).exists()
            product = request.env['product.template'].sudo().search([('cr_template_ref', '=', storeProductTemplateId)])
            received_signature = request.httprequest.headers.get('signature', '')
            auth = product.is_temp_available(received_signature)
            if is_storeProductTemplateId_exist:
                if auth:
                    product.msg_notification_from_gelato(data_info['event'])

        if data_info['event'] == 'store_product_template_deleted':
            storeProductTemplateId = data_info['storeProductTemplateId']
            _logger.info(f"storeProductTemplateId {storeProductTemplateId}")
            is_storeProductTemplateId_exist = request.env['product.template'].sudo().search(
                [('cr_template_ref', '=', storeProductTemplateId)]).exists()
            product = request.env['product.template'].sudo().search([('cr_template_ref', '=', storeProductTemplateId)])
            received_signature = request.httprequest.headers.get('signature', '')
            auth = product.is_temp_available(received_signature)
            if is_storeProductTemplateId_exist:
                if auth:
                    product.msg_notification_from_gelato(data_info['event'])
                    cr_sale = request.env['sale.order.line'].sudo().search([('product_template_id', '=', product.id)])
                    for data in cr_sale:
                        data.order_id.with_user(2)._action_cancel()
                        data.order_id.with_user(2).unlink()

                    product.with_user(2).unlink()

        if data_info['event'] == 'store_product_template_created':
            product = request.env['product.template'].sudo().create({
                'name': data_info['title'],
                'cr_template_ref': data_info['storeProductTemplateId'],
            })
            if product:
                product.action_sync_gelato_template_info()
                product.set_img()

        return request.make_json_response('')

    def order_status_event(self, sale, data_info):
        if sale:
            status = data_info.get('fulfillmentStatus')
            if status == "created":
                sale.msg_notification_from_gelato(status)
            elif status == "uploading":
                sale.msg_notification_from_gelato(status)
            elif status == "passed":
                sale.msg_notification_from_gelato(status)
            elif status == "in_production":
                sale.msg_notification_from_gelato(status)
            elif status == "printed":
                sale.msg_notification_from_gelato(status)
            elif status == "draft":
                sale.msg_notification_from_gelato(status)
            elif status == "failed":
                sale.msg_notification_from_gelato(status)
            elif status == "canceled":
                sale.msg_notification_from_gelato(status)
                if sale.state != 'cancel':
                    sale.with_user(2)._action_cancel()
            elif status == "pending_approval":
                sale.msg_notification_from_gelato(status)
            elif status == "pending_personalization":
                sale.msg_notification_from_gelato(status)
            elif status == "digitizing":
                sale.msg_notification_from_gelato(status)
            elif status == "not_connected":
                sale.msg_notification_from_gelato(status)
            elif status == "on_hold":
                sale.msg_notification_from_gelato(status)
            elif status == "shipped":
                sale.msg_notification_from_gelato(status)
            elif status == "in_transit":
                sale.msg_notification_from_gelato(status)
            elif status == "delivered":
                sale.msg_notification_from_gelato(status)
            elif status == "returned":
                sale.msg_notification_from_gelato(status)
            else:
                sale.msg_notification_from_gelato(status)


    @staticmethod
    def is_notification_from_Correct_webhook(sale_id, received_signature):
        if sale_id.company_id.sudo().webhook_secret_for_gelato != received_signature:
            _logger.warning("Received notification with invalid signature.")
        else:
            return True

