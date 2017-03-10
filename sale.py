# This file is part of the sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
#! -*- coding: utf8 -*-
from decimal import Decimal
from trytond.model import ModelView, fields, ModelSQL
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Bool, Eval, Not
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button, StateAction
from trytond import backend
from trytond.tools import grouped_slice

__all__ = ['Sale', 'WarehouseStock', 'WizardWarehouseStock', 'ProductLine',
'SaleWarehouse', 'SalePriceList']
__metaclass__ = PoolMeta
_ZERO = Decimal('0.0')

class Sale():
    'Sale'
    __name__ = 'sale.sale'

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls._buttons.update({
                'warehouse_stock': {
                    'invisible': ((Eval('state') != 'draft') | (Eval('invoice_state') != 'none')),
                    },
                })
    @classmethod
    @ModelView.button_action('nodux_sale_pos_warehouse.warehouse_stock')
    def warehouse_stock(cls, sales):
        pass

class SaleWarehouse(ModelView, ModelSQL):
    'Producto por Bodega'
    __name__ = 'sale.warehouse'

    sale = fields.Many2One('sale.sale', 'Sale', readonly = True)
    product = fields.Char('Producto',  readonly = True)
    warehouse = fields.Char('Bodega',  readonly = True)
    quantity = fields.Char('Cantidad', readonly = True)

class SalePriceList(ModelView, ModelSQL):
    'Sale Price List'
    __name__ = 'sale.list_by_product'

    sale = fields.Many2One('sale.sale', 'Sale', readonly = True)
    lista_precio = fields.Char('Lista de Precio')
    fijo = fields.Numeric('Precio sin IVA', digits=(16, 6))
    fijo_con_iva = fields.Numeric('Precio con IVA', digits=(16, 6))

class ProductLine(ModelView, ModelSQL):
    'Product Line'
    __name__ = 'product.product.line'

    sequence = fields.Integer('Sequence')
    product = fields.Many2One('product.product', 'Producto')
    revisar = fields.Boolean('Verificar Stock')
    precio_venta = fields.Numeric('Precio Venta')
    total_stock = fields.Integer('Total Stock')
    add = fields.Boolean('Agregar en Venta')
    quantity = fields.Numeric('Cantidad')

class WarehouseStock(ModelView):
    'Warehouse Stock'
    __name__ = 'nodux_sale_pos_warehouse.warehouse'
    producto = fields.Char('Producto')
    lines = fields.One2Many('product.product.line', None, 'Lines')
    all_list_price = fields.One2Many('sale.list_by_product', 'sale', 'Price List', readonly=True)
    warehouse_sale =fields.One2Many('sale.warehouse', 'sale', 'Productos por bodega', readonly=True)

    @fields.depends('producto', 'lines')
    def on_change_producto(self):
        pool = Pool()
        Product = pool.get('product.product')
        Location = pool.get('stock.location')
        location = Location.search([('type', '=', 'warehouse')])
        Move = pool.get('stock.move')
        in_s = 0
        stock = 0
        s_total = 0
        stock_total = 0

        res = {}
        res['lines'] = {}
        if self.lines:
            res['lines']['remove'] = [x['id'] for x in self.lines]

        if not self.producto:
            return res

        code = self.producto+'%'
        name = self.producto+'%'

        products = Product.search([('code', 'like', code)])
        if products:
            for product in products:

                stock_total = 0
                for lo in location:
                    in_stock = Move.search_count([('product', '=',  product), ('to_location','=', lo.storage_location)])
                    move = Move.search_count([('product', '=', product), ('from_location','=', lo.storage_location)])
                    s_total = in_stock - move
                    stock_total += s_total

                product_line = {
                    'product': product.id,
                    'precio_venta':product.list_price,
                    'total_stock':stock_total,
                }
                res['lines'].setdefault('add', []).append((0, product_line))
        else:
            products = Product.search([('name', 'ilike', name)])
            for product in products:

                stock_total = 0
                for lo in location:
                    in_stock = Move.search_count([('product', '=',  product), ('to_location','=', lo.storage_location)])
                    move = Move.search_count([('product', '=', product), ('from_location','=', lo.storage_location)])

                    s_total = in_stock - move
                    stock_total += s_total

                product_line = {
                    'product': product.id,
                    'precio_venta':product.list_price,
                    'total_stock':stock_total,
                }
                res['lines'].setdefault('add', []).append((0, product_line))
        print "res ", res
        return res


    @fields.depends('lines', 'all_list_price', 'warehouse_sale', 'producto')
    def on_change_lines(self):
        pool = Pool()
        Move = pool.get('stock.product_quantities_warehouse')
        Location = pool.get('stock.location')
        location = Location.search([('type', '=', 'warehouse')])
        Product = pool.get('product.product')
        Line = pool.get('sale.line')
        Template = pool.get('product.template')
        Move = pool.get('stock.move')
        StockLine = pool.get('stock.inventory.line')
        stock = 0
        in_s = 0
        Tax = pool.get('account.tax')
        Invoice = pool.get('account.invoice')
        Configuration = pool.get('account.configuration')
        config = Configuration(1)

        changes = {}
        changes['all_list_price'] = {}
        changes['warehouse_sale'] = {}
        changes['lines'] = {}

        if self.warehouse_sale:
            changes['warehouse_sale']['remove'] = [x['id'] for x in self.warehouse_sale]
        if self.all_list_price:
            changes['all_list_price']['remove'] = [x['id'] for x in self.all_list_price]

        cont = 0
        if self.lines:
            for line in self.lines:
                cont += 1
                if line.revisar == True:
                    result_line = {
                        'revisar': False,
                        'product': line.product.id,
                        'precio_venta': line.precio_venta,
                        'total_stock': line.total_stock,
                        'add': line.add,
                        'quantity': line.quantity,
                    }
                    changes['lines']['remove'] = [line['id']]

                    changes['lines'].setdefault('add', []).append((cont-1, result_line))

                    for list_p in line.product.listas_precios:
                        result_list = {
                            'lista_precio': list_p.lista_precio.name,
                            'fijo': list_p.fijo,
                            'fijo_con_iva': list_p.fijo_con_iva,
                        }
                        changes['all_list_price'].setdefault('add', []).append((0, result_list))

                    for lo in location:
                        in_stock = Move.search_count([('product', '=',  line.product), ('to_location','=', lo.storage_location)])
                        move = Move.search_count([('product', '=', line.product), ('from_location','=', lo.storage_location)])

                        s_total = in_stock - move

                        result = {
                            'product': line.product.name,
                            'warehouse': lo.name,
                            'quantity': str(int(s_total)),
                        }
                        stock = 0
                        in_s = 0
                        changes['warehouse_sale'].setdefault('add', []).append((0, result))

        return changes

class WizardWarehouseStock(Wizard):
    'Wizard Warehouse Stock'
    __name__ = 'nodux_sale_pos_warehouse.warehouse_stock'

    start = StateView('nodux_sale_pos_warehouse.warehouse',
        'nodux_sale_pos_warehouse.warehouse_stock_view_form', [
            Button('Close', 'end', 'tryton-cancel'),
            Button('Add', 'add_', 'tryton-ok'),
        ])

    add_ = StateTransition()

    def add_lines(self):
        pool = Pool()
        Line = pool.get('sale.line')
        for line_add in self.start.lines:
            if line_add.add == True:
                sale = Transaction().context.get('active_id', False)
                line = Line()
                line.product = line_add.product
                update = line.on_change_product()
                line.unit_digits = update['unit_digits']
                line.gross_unit_price = update['gross_unit_price']
                line.taxes = update['taxes']
                line.gross_unit_price_wo_round = update['gross_unit_price_wo_round']
                line.description = update['description']
                if line_add.quantity:
                    line.quantity = line_add.quantity
                else:
                    line.quantity = 1
                line.sale = sale
                line.save()

    def transition_add_(self):
        self.add_lines()
        return 'end'
