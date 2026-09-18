from odoo import _, fields, models
from odoo.exceptions import UserError


class ProductDocument(models.Model):

    _inherit = 'product.document'

    is_gelato = fields.Boolean(readonly=True)

    def _prepare_file_for_gelato(self):
        if not self.datas:
            raise UserError(_("Make sure to add a print image to each item before placing your order."))

        cr_query_string = f'access_token={self.ir_attachment_id.generate_access_token()[0]}'
        cr_url = f'{self.get_base_url()}{self.ir_attachment_id.image_src}?{cr_query_string}'
        return {
            'type': self.name.lower(),
            'url': cr_url,
        }
