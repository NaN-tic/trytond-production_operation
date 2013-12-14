from decimal import Decimal

from trytond.model import fields, ModelSQL, ModelView, Workflow
from trytond.pool import PoolMeta
from trytond.pyson import Eval

__all__ = ['WorkCenterCategory', 'WorkCenter', 'Route', 'RouteOperation',
    'Operation', 'OperationLine', 'Production']
__metaclass__ = PoolMeta


class WorkCenterCategory(ModelSQL, ModelView):
    'Work Center Category'
    __name__ = 'production.work_center.category'
    name = fields.Char('Name', required=True)
    cost_price = fields.Numeric('Cost Price', digits=(16, 4), required=True)
    uom = fields.Many2One('product.uom', 'Uom', required=True)


class WorkCenter(ModelSQL, ModelView):
    'Work Center'
    __name__ = 'production.work_center'
    name = fields.Char('Name', required=True)
    category = fields.Many2One('production.work_center.category', 'Category')
    type = fields.Selection([
            ('machine', 'Machine'),
            ('employee', 'Employee'),
            ], 'Type')
    employee = fields.Many2One('company.employee', 'Employee', states={
            'invisible': Eval('type') != 'employee',
            'required': Eval('type') == 'employee',
            }, depends=['type'])
    cost_price = fields.Numeric('Cost Price', digits=(16, 4), required=True)
    uom = fields.Many2One('product.uom', 'Uom', required=True)


class Route(ModelSQL, ModelView):
    'Production Route'
    __name__ = 'production.route'
    name = fields.Char('Name', required=True)
    operations = fields.One2Many('production.route.operation', 'bom',
        'Operations')

class OperationType(ModelSQL, ModelView):
    'Operation Type'
    __name__ = 'production.operation.type'

    name = fields.Char('Name', required=True)



class RouteOperation(ModelSQL, ModelView):
    'Route Operation'
    __name__ = 'production.route.operation'
    route = fields.Many2One('production.route', 'Route', required=True)
    name = fields.Char('Name', required=True)
    sequence = fields.Integer('Sequence')
    work_center = fields.Many2One('production.work_center', 'Work Center')
    work_center_category = fields.Many2One('production.work_center', 'Work Center')
    operation_type = fields.Many2One('production.operation.type', 'Operation Type')

    @classmethod
    def __setup__(cls):
        super(RouteOperation, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == None, table.sequence]


class Operation(ModelSQL, ModelView):
    'Operation'
    __name__ = 'production.operation'
    production = fields.Many2One('production', 'Production', required=True)
    name = fields.Char('Name', required=True)
    sequence = fields.Integer('Sequence')
    work_center = fields.Many2One('production.work_center', 'Work Center')
    route_operation = fields.Many2One('production.route.operation',
        'Route Operation')
    lines = fields.One2Many('production.operation.line', 'operation', 'Lines')
    cost = fields.Function(fields.Numeric('Cost'), 'get_cost')
    operation_type = fields.Many2One('production.operation.type', 'Operation Type')

    # TODO: Add workflow

    @classmethod
    def __setup__(cls):
        super(Operation, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == None, table.sequence]

    def get_cost(self, name):
        # TODO
        return Decimal('0.0')


class OperationLine(ModelSQL, ModelView):
    'Operation Line'
    __name__ = 'production.operation.line'
    operation = fields.Many2One('production.operation', 'Operation',
        required=True)
    work_center = fields.Function(fields.Many2One('production.work_center',
            'Work Center', on_change_with=['operation']),
        'on_change_with_work_center')
    # Maybe start and end in a new module?
    start = fields.DateTime('Start')
    end = fields.DateTime('End')
    quantity = fields.Float('Quantity')
    uom = fields.Many2One('product.uom', 'Uom', required=True)
    cost = fields.Function(fields.Numeric('Cost'), 'get_cost')

    def get_cost(self, name):
        # TODO
        return Decimal('0.0')

    def on_change_with_work_center(self, name=None):
        return (self.operation.work_center.id
            if self.operation and self.operation.work_center else None)


class Production:
    __name__ = 'production'
    route = fields.Many2One('production.route', 'Route',
        on_change=['route', 'operations'])
    operations = fields.One2Many('production.operation', 'production',
        'Operations')

    def update_operations(self):
        if not self.route:
            return {}
        operations = {
            'remove': [x.id for x in self.operations],
            'add': [],
            }
        changes = {
            'operations': operations,
            }
        for operation in self.route.operations:
            operations['add'].append({
                    'name': operation.name,
                    'sequence': operation.sequence,
                    'work_center': (operation.work_center.id
                        if operation.work_center else None),
                    'route_operation': operation.id,
                    })
        return changes

    def on_change_route(self):
        return self.update_operations()

    def get_cost(self, name):
        cost = super(Production, self).get_cost(name)
        for operation in self.operations:
            cost += operation.cost
        return cost
