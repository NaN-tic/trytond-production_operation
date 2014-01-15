from decimal import Decimal

from trytond.model import fields, ModelSQL, ModelView, Workflow
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction

__all__ = ['Operation', 'OperationTracking', 'Production']
__metaclass__ = PoolMeta

STATES = {
    'readonly': Eval('state').in_(['running', 'done'])
    }
DEPENDS = ['state']


class Operation(Workflow, ModelSQL, ModelView):
    'Operation'
    __name__ = 'production.operation'

    production = fields.Many2One('production', 'Production', required=True,
        states=STATES, depends=DEPENDS)
    sequence = fields.Integer('Sequence', states=STATES, depends=DEPENDS)
    work_center_category = fields.Many2One('production.work_center.category',
        'Work Center Category', states=STATES, depends=DEPENDS, required=True)
    work_center = fields.Many2One('production.work_center', 'Work Center',
        states=STATES, depends=DEPENDS + ['work_center_category'], domain=[
            ('category', '=', Eval('work_center_category'),
            )])
    route_operation = fields.Many2One('production.route.operation',
        'Route Operation', states=STATES, depends=DEPENDS)
    lines = fields.One2Many('production.operation.tracking', 'operation',
        'Lines', states=STATES, depends=DEPENDS, context={
            'work_center_category': Eval('work_center_category'),
            'work_center': Eval('work_center'),
            })
    cost = fields.Function(fields.Numeric('Cost'), 'get_cost')
    operation_type = fields.Many2One('production.operation.type',
        'Operation Type', states=STATES, depends=DEPENDS, required=True)
    uom_category = fields.Function(fields.Many2One(
            'product.uom.category', 'Uom Category', on_change_with=[
                'work_center_category', 'work_center']),
        'on_change_with_uom_category')
    state = fields.Selection([
            ('planned', 'Planned'),
            ('waiting', 'Waiting'),
            ('running', 'Running'),
            ('done', 'Done'),
            ], 'State', readonly=True)

    @classmethod
    def __setup__(cls):
        super(Operation, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))
        cls._invalid_production_states_on_create = ['done']
        cls._error_messages.update({
                'invalid_production_state': ('You can not create an operation'
                    ' for Production "%s".'),
                })
        cls._transitions |= set((
                ('planned', 'waiting'),
                ('waiting', 'running'),
                ('running', 'waiting'),
                ('running', 'done'),
                ))
        cls._buttons.update({
                'wait': {
                    'invisible': ~Eval('state').in_(['planned', 'running']),
                    'icon': If(Eval('state') == 'running',
                        'tryton-go-previous', 'tryton-go-next')
                    },
                'run': {
                    'invisible': Eval('state') != 'waiting',
                    'icon': 'tryton-go-next',
                    },
                'done': {
                    'invisible': Eval('state') != 'running',
                    },
                })

    @staticmethod
    def default_state():
        return 'planned'

    def get_rec_name(self, name):
        if self.operation_type:
            return self.operation_type.rec_name
        return super(Operation, self).get_rec_name()

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('operation_type.name',) + tuple(clause[1:])]

    def on_change_with_uom_category(self, name=None):
        if self.work_center_category:
            return self.work_center_category.uom.category.id
        if self.work_center:
            return self.work_center.uom.category.id

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Production = pool.get('production')
        productions = []
        for value in vlist:
            productions.append(value['production'])

        invalid_productions = Production.search([
                ('id', 'in', productions),
                ('state', 'in', cls._invalid_production_states_on_create),
                ], limit=1)
        if invalid_productions:
            production, = invalid_productions
            cls.raise_user_error('invalid_production_state',
                production.rec_name)
        super(Operation, cls).create(vlist)

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [table.sequence == None, table.sequence]

    def get_cost(self, name):
        cost = Decimal('0.0')
        for line in self.lines:
            cost += line.cost
        return cost

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, operations):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('running')
    def run(cls, operations):
        pass

    @classmethod
    def done(cls, operations):
        pool = Pool()
        Production = pool.get('production')

        productions = set([o.production for o in operations])
        cls.write(operations, {'state': 'done'})

        with Transaction().set_context(from_done_operation=True):
            Production.done(productions)


class OperationTracking(ModelSQL, ModelView):
    'operation.tracking'
    __name__ = 'production.operation.tracking'

    operation = fields.Many2One('production.operation', 'Operation',
        required=True)
    uom = fields.Many2One('product.uom', 'Uom', required=True,
        on_change_with=['operation'], domain=[
            If(Bool(Eval('_parent_operation', 0)),
                ('category', '=', Eval('_parent_operation', {}).get(
                        'uom_category', 0)), (),
                )])
    unit_digits = fields.Function(fields.Integer('Unit Digits',
            on_change_with=['uom']), 'on_change_with_unit_digits')
    quantity = fields.Float('Quantity', required=True,
        digits=(16, Eval('unit_digits', 2)), depends=['unit_digits'])
    cost = fields.Function(fields.Numeric('Cost'), 'get_cost')

    @staticmethod
    def default_quantity():
        return 0.0

    @staticmethod
    def default_uom():
        WorkCenter = Pool().get('production.work_center')
        WorkCenterCategory = Pool().get('production.work_center.category')

        context = Transaction().context
        if context.get('work_center'):
            work_center = WorkCenter(context['work_center'])
            return work_center.uom.id
        if context.get('work_center_category'):
            category = WorkCenterCategory(context['work_center_category'])
            return category.uom.id

    def get_cost(self, name):
        Uom = Pool().get('product.uom')
        work_center = self.operation.work_center
        if not work_center:
            return Decimal('0.0')
        quantity = Uom.compute_qty(self.uom, self.quantity,
            work_center.uom)
        return Decimal(str(quantity)) * work_center.cost_price

    def on_change_with_uom(self):
        if self.operation.work_center:
            return self.operation.work_center.uom.id

    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2


class Production:
    __name__ = 'production'

    route = fields.Many2One('production.route', 'Route',
        on_change=['route', 'operations'], states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            })
    operations = fields.One2Many('production.operation', 'production',
        'Operations', order=[('sequence', 'ASC')], states={
            'readonly': Eval('state') == 'done',
            })

    @classmethod
    def __setup__(cls):
        super(Production, cls).__setup__()
        cls._error_messages.update({
                'pending_operations': ('Production "%(production)s" can not be'
                    ' done because their operation "%(operation)s" is not '
                    'done.'),
                'no_work_center': ('We can not found any work center for '
                    'Operation "%s".'),
                })

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
                    'sequence': operation.sequence,
                    'work_center_category': operation.work_center_category.id,
                    'work_center': (operation.work_center.id
                        if operation.work_center else None),
                    'operation_type': (operation.operation_type.id
                        if operation.operation_type else None),
                    'route_operation': operation.id,
                    })
        return changes

    def on_change_route(self):
        return self.update_operations()

    @classmethod
    def run(cls, productions):
        pool = Pool()
        Operation = pool.get('production.operation')

        super(Production, cls).run(productions)

        operations = []
        for production in productions:
            operations.extend(production.operations)

        if operations:
            Operation.wait(operations)

    @classmethod
    def done(cls, productions):
        pool = Pool()
        Operation = pool.get('production.operation')
        Template = pool.get('product.template')
        Product = pool.get('product.product')

        pending_operations = Operation.search([
                ('production', 'in', [p.id for p in productions]),
                ('state', '!=', 'done'),
                ], limit=1)
        if pending_operations:
            if Transaction().context.get('from_done_operation', False):
                return
            operation, = pending_operations
            cls.raise_user_error('pending_operations', error_args={
                    'production': operation.production.rec_name,
                    'operation': operation.rec_name,
                    })

        if hasattr(Product, 'cost_price'):
            digits = Product.cost_price.digits
        else:
            digits = Template.cost_price.digits

        for production in productions:
            operation_cost = sum(o.cost for o in production.operations)
            total_quantity = Decimal(str(sum(o.quantity for o in
                        production.outputs)))
            added_unit_price = Decimal(operation_cost / total_quantity
                ).quantize(Decimal(str(10 ** -digits[1])))
            for output in production.outputs:
                output.unit_price += added_unit_price
                output.save()

        super(Production, cls).done(productions)

    def get_cost(self, name):
        cost = super(Production, self).get_cost(name)
        for operation in self.operations:
            cost += operation.cost
        return cost
