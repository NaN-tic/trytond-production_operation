# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import operation
from . import configuration


def register():
    Pool.register(
        configuration.Configuration,
        operation.Operation,
        operation.OperationTracking,
        operation.Production,
        module='production_operation', type_='model')
