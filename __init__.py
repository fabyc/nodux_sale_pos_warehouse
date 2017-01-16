# This file is part of the sale_payment module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

from trytond.pool import Pool
from .sale import *
def register():
    Pool.register(
        Sale,
        WarehouseStock,
        ProductLine,
        module='nodux_sale_pos_warehouse', type_='model')
    Pool.register(
        WizardWarehouseStock,
        module='nodux_sale_pos_warehouse', type_='wizard')
