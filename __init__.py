# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

from trytond.pool import Pool
from .operation import *

def register():
    Pool.register(
        Operation,
        OperationTracking,
        Production,
        module='production_operation', type_='model')
