from odoo import fields, models, api
from odoo.exceptions import ValidationError
from datetime import datetime

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    sale_currency_id = fields.Many2one('res.currency',string='Moneda Precio de Venta')

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_display_price(self, product):
        # TO DO: move me in master/saas-16 on sale.order
        # awa: don't know if it's still the case since we need the "product_no_variant_attribute_value_ids" field now
        # to be able to compute the full price

        # it is possible that a no_variant attribute is still in a variant if
        # the type of the attribute has been changed after creation.
        no_variant_attributes_price_extra = [
            ptav.price_extra for ptav in self.product_no_variant_attribute_value_ids.filtered(
                lambda ptav:
                    ptav.price_extra and
                    ptav not in product.product_template_attribute_value_ids
            )
        ]
        if no_variant_attributes_price_extra:
            product = product.with_context(
                no_variant_attributes_price_extra=tuple(no_variant_attributes_price_extra)
            )

        if self.order_id.pricelist_id.discount_policy == 'with_discount':
            res = product.with_context(pricelist=self.order_id.pricelist_id.id).price
            # Moneda del pedido es en USD y el precio de venta del producto esta en USD
            if self.product_id.product_tmpl_id.sale_currency_id and self.order_id.currency_id.id != self.order_id.company_id.currency_id.id and \
                    self.product_id.product_tmpl_id.sale_currency_id.id != self.company_id.currency_id.id:
                res = res / self.order_id.currency_rate
            # Moneda del pedido es en ARS y el precio de venta del producto es en USD
            if self.product_id.product_tmpl_id.sale_currency_id and self.order_id.currency_id.id == self.order_id.company_id.currency_id.id and \
                    self.product_id.product_tmpl_id.sale_currency_id.id != self.order_id.company_id.currency_id.id:
                currency_rate = self.product_id.product_tmpl_id.sale_currency_id.rate
                res = res / currency_rate
            return res
        product_context = dict(self.env.context, partner_id=self.order_id.partner_id.id, date=self.order_id.date_order, uom=self.product_uom.id)

        final_price, rule_id = self.order_id.pricelist_id.with_context(product_context).get_product_price_rule(self.product_id, self.product_uom_qty or 1.0, self.order_id.partner_id)
        base_price, currency = self.with_context(product_context)._get_real_price_currency(product, rule_id, self.product_uom_qty, self.product_uom, self.order_id.pricelist_id.id)
        if currency != self.order_id.pricelist_id.currency_id:
            base_price = currency._convert(
                base_price, self.order_id.pricelist_id.currency_id,
                self.order_id.company_id or self.env.company, self.order_id.date_order or fields.Date.today())
        # negative discounts (= surcharge) are included in the display price
        return max(base_price, final_price)

