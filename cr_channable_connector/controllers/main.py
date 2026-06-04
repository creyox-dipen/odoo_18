# -*- coding: utf-8 -*-
# Part of Creyox Technologies
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ChannableFeedController(http.Controller):

    @http.route('/channable/feed/<string:feed_token>', type='http', auth='public', methods=['GET'], csrf=False)
    def channable_feed(self, feed_token, **kwargs):
        """Generates and returns the XML product feed for the specified marketplace."""
        # Find the marketplace with the matching feed token
        marketplace = request.env['channable.marketplace'].sudo().search([('feed_token', '=', feed_token)], limit=1)
        if not marketplace:
            return request.not_found()

        # Get active and saleable products that have a value in the sync product field
        sync_field = marketplace.sync_product_field or 'default_code'
        domain = [
            ('sale_ok', '=', True),
            (sync_field, '!=', False),
            (sync_field, '!=', ''),
        ]
        
        products = request.env['product.product'].sudo().search(domain)
        
        # Get active attribute mappings for this marketplace
        mappings = marketplace.attribute_mapping_ids
        
        # Build XML dynamically using string builder to avoid encoding issues
        xml_elements = ['<?xml version="1.0" encoding="utf-8"?>']
        xml_elements.append('<products>')
        
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        
        for product in products:
            # Retrieve quantity available in the context of the marketplace's warehouse
            stock_qty = product.with_context(warehouse=marketplace.warehouse_id.id).qty_available
            stock_qty = int(stock_qty) if stock_qty > 0 else 0
            
            # Retrieve identifier mapped to Channable
            channable_id = getattr(product, sync_field)
            if not channable_id:
                continue
                
            xml_elements.append('  <product>')
            xml_elements.append(f'    <id>{channable_id}</id>')
            xml_elements.append(f'    <title><![CDATA[{product.name or ""}]]></title>')
            
            # Description (using sale description if present, else fallback to product name)
            description = product.description_sale or product.name or ""
            xml_elements.append(f'    <description><![CDATA[{description}]]></description>')
            
            # Price (using pricelist if available, fallback to list_price)
            price = product.list_price or 0.0
            if marketplace.pricelist_id:
                try:
                    price = marketplace.pricelist_id._get_product_price(product, 1.0)
                except Exception:
                    try:
                        price = marketplace.pricelist_id.price_get(product.id, 1.0)[marketplace.pricelist_id.id]
                    except Exception:
                        pass
            xml_elements.append(f'    <price>{price:.2f}</price>')
            
            # Stock
            xml_elements.append(f'    <stock>{stock_qty}</stock>')
            
            # EAN/Barcode
            ean = product.barcode or ""
            xml_elements.append(f'    <ean>{ean}</ean>')
            
            # SKU/Internal Reference
            sku = product.default_code or ""
            xml_elements.append(f'    <sku>{sku}</sku>')
            
            # Brand (fallback to seller or company name)
            brand = ""
            if product.seller_ids:
                brand = product.seller_ids[0].partner_id.name or ""
            if not brand:
                brand = request.env.company.name or ""
            xml_elements.append(f'    <brand><![CDATA[{brand}]]></brand>')
            
            # Category
            category = product.categ_id.complete_name or product.categ_id.name or ""
            xml_elements.append(f'    <category><![CDATA[{category}]]></category>')
            
            # Weight
            weight = product.weight or 0.0
            xml_elements.append(f'    <weight>{weight:.2f}</weight>')
            
            # Image Link
            image_link = f"{base_url}/web/image/product.product/{product.id}/image_1920"
            xml_elements.append(f'    <image_link><![CDATA[{image_link}]]></image_link>')
            
            # Product Link
            link = f"{base_url}/web#id={product.id}&model=product.product&view_type=form"
            xml_elements.append(f'    <link><![CDATA[{link}]]></link>')
            
            # Dynamic Attribute Mappings
            for mapping in mappings:
                tag = mapping.target_tag
                val = ""
                if mapping.mapping_type == 'field' and mapping.field_id:
                    field_name = mapping.field_id.name
                    try:
                        raw_val = product[field_name]
                        if raw_val:
                            if hasattr(raw_val, 'display_name'):
                                val = raw_val.display_name
                            elif hasattr(raw_val, 'name'):
                                val = raw_val.name
                            else:
                                val = str(raw_val)
                    except Exception:
                        pass
                elif mapping.mapping_type == 'attribute' and mapping.attribute_id:
                    attribute_id = mapping.attribute_id.id
                    matching_value = product.product_template_attribute_value_ids.filtered(
                        lambda v: v.attribute_id.id == attribute_id
                    )
                    if matching_value:
                        val = matching_value.name or ""
                
                if val:
                    if any(c in val for c in ('&', '<', '>', '"', "'")):
                        xml_elements.append(f'    <{tag}><![CDATA[{val}]]></{tag}>')
                    else:
                        xml_elements.append(f'    <{tag}>{val}</{tag}>')
            
            xml_elements.append('  </product>')
            
        xml_elements.append('</products>')
        
        xml_content = "\n".join(xml_elements)
        
        return request.make_response(
            xml_content,
            headers=[
                ('Content-Type', 'application/xml; charset=utf-8'),
                ('Content-Length', str(len(xml_content.encode('utf-8')))),
            ]
        )
