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
        Lines = pool.get('product.product.line')
        product_line = Lines()
        lines = []
        location = Location.search([('type', '=', 'warehouse')])
        Move = pool.get('stock.move')
        in_s = 0
        stock = 0
        s_total = 0
        stock_total = 0

        if self.lines:
            self.lines = lines

        if not self.producto:
            return

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

                product_line.product = product.id
                product_line.precio_venta = product.list_price
                product_line.total_stock = stock_total

                lines.append(product_line)
        else:
            print "Ingresa aqui "
            products = Product.search([('name', 'ilike', name)])
            for product in products:

                stock_total = 0
                for lo in location:
                    in_stock = Move.search_count([('product', '=',  product), ('to_location','=', lo.storage_location)])
                    move = Move.search_count([('product', '=', product), ('from_location','=', lo.storage_location)])

                    s_total = in_stock - move
                    stock_total += s_total

                product_line.product = product.id
                product_line.precio_venta = product.list_price
                product_line.total_stock = stock_total

                lines.append(product_line)
                print "Lineas ", lines
        self.lines = lines


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
        ProductLine = pool.get('product.product.line')
        ListbyProduct = pool.get('sale.list_by_product')
        SaleWarehouse = pool.get('sale.warehouse')

        warehouse_sale = []
        all_list_price = []
        lines = []

        if self.warehouse_sale:
            self.warehouse_sale = warehouse_sale
        if self.all_list_price:
            self.all_list_price = all_list_price

        cont = 0
        if self.lines:
            for line in self.lines:
                cont += 1
                if line.revisar == True:
                    result_line = ProductLine()
                    result_line.revisar = False
                    result_line.product = line.product.id
                    result_line.precio_venta = line.precio_venta
                    result_line.total_stock = line.total_stock
                    result_line.add = line.add
                    result_line.quantity = line.quantity
                    line.revisar = False
                    #changes['lines']['remove'] = [line['id']]

                    #changes['lines'].setdefault('add', []).append((cont-1, result_line))

                    for list_p in line.product.listas_precios:
                        result_list = ListbyProduct()
                        result_list.lista_precio = list_p.lista_precio.name
                        result_list.fijo = list_p.fijo
                        result_list.fijo_con_iva = list_p.fijo_con_iva
                        all_list_price.append(result_list)

                    for lo in location:
                        in_stock = Move.search_count([('product', '=',  line.product), ('to_location','=', lo.storage_location)])
                        move = Move.search_count([('product', '=', line.product), ('from_location','=', lo.storage_location)])

                        s_total = in_stock - move

                        result = SaleWarehouse()
                        result.product = line.product.name
                        result.warehouse = lo.name
                        result.quantity = str(int(s_total))

                        stock = 0
                        in_s = 0
                        warehouse_sale.append(result)

        self.warehouse_sale = warehouse_sale
        self.all_list_price = all_list_price

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
