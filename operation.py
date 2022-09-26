from decimal import Decimal
from trytond.model import (fields, ModelSQL, ModelView, Workflow,
    sequence_ordered)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If, Id, Bool
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserWarning, UserError


__all__ = ['Operation', 'OperationTracking', 'Production']

STATES = {
    'readonly': Eval('state').in_(['running', 'done'])
    }
DEPENDS = ['state']


class Operation(sequence_ordered(), Workflow, ModelSQL, ModelView):
    'Operation'
    __name__ = 'production.operation'

    production = fields.Many2One('production', 'Production', required=True,
        states=STATES, depends=DEPENDS, ondelete='CASCADE')
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
    total_quantity = fields.Function(fields.Float('Total Quantity'),
        'get_total_quantity')
    operation_type = fields.Many2One('production.operation.type',
        'Operation Type', states=STATES, depends=DEPENDS, required=True)
    state = fields.Selection([
            ('cancelled', 'Canceled'),
            ('planned', 'Planned'),
            ('waiting', 'Waiting'),
            ('running', 'Running'),
            ('done', 'Done'),
            ], 'State', readonly=True)
    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'get_company', searcher='search_company')

    @classmethod
    def __setup__(cls):
        super(Operation, cls).__setup__()
        cls._invalid_production_states_on_create = ['done']
        cls._transitions |= set((
                ('planned', 'cancelled'),
                ('planned', 'waiting'),
                ('waiting', 'running'),
                ('running', 'waiting'),
                ('running', 'done'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': Eval('state') != 'planned',
                    },
                'wait': {
                    'invisible': ~Eval('state').in_(['planned', 'running']),
                    'icon': If(Eval('state') == 'running',
                        'tryton-back', 'tryton-forward')
                    },
                'run': {
                    'invisible': Eval('state') != 'waiting',
                    'icon': 'tryton-forward',
                    },
                'done': {
                    'invisible': Eval('state') != 'running',
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()

        super(Operation, cls).__register__(module_name)

        # Migration from 5.6: rename state cancel to cancelled
        cursor.execute(*sql_table.update(
                [sql_table.state], ['cancelled'],
                where=sql_table.state == 'cancel'))

    @staticmethod
    def default_state():
        return 'planned'

    def get_company(self, name):
        return self.production.company.id if self.production.company else None

    @classmethod
    def search_company(cls, name, clause):
        return [('production.company',) + tuple(clause[1:])]

    def get_rec_name(self, name):
        res = ''
        if self.operation_type:
            res = self.operation_type.rec_name + ' @ '
        if self.production:
            res += self.production.rec_name
        return res

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('operation_type.name',) + tuple(clause[1:]),
            ('production',) + tuple(clause[1:]),
            ]

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Production = pool.get('production')
        Warning = pool.get('res.user.warning')
        productions = []
        for value in vlist:
            productions.append(value['production'])

        invalid_productions = Production.search([
                ('id', 'in', productions),
                ('state', 'in', ['done']),
                ], limit=1)

        if invalid_productions:
            production, = invalid_productions
            key = 'invalid_production_state_%s' % production.id
            if Warning.check(key):
                raise UserWarning(key, gettext(
                    'production_operation.invalid_production_state',
                    production=production.rec_name))
        return super(Operation, cls).create(vlist)

    @classmethod
    def copy(cls, operations, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('state', 'planned')
        default.setdefault('lines', [])
        return super(Operation, cls).copy(operations, default)

    def get_cost(self, name):
        cost = Decimal('0.0')
        for line in self.lines:
            cost += line.cost
        return cost

    def get_total_quantity(self, name):
        Uom = Pool().get('product.uom')

        total = 0.
        for line in self.lines:
            if not line.uom or not line.quantity:
                continue
            total += Uom.compute_qty(line.uom, line.quantity,
                self.work_center_category.uom)
        return total

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, operations):
        pass

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
        to_done = []
        for production in productions:
            to_do = True
            for operation in production.operations:
                if operation.state != 'done':
                    to_do = False
                    break
            if to_do:
                to_done.append(production)
        Production.done(to_done)


class OperationTracking(ModelSQL, ModelView):
    'operation.tracking'
    __name__ = 'production.operation.tracking'

    operation = fields.Many2One('production.operation', 'Operation',
        required=True, ondelete='CASCADE')
    uom = fields.Many2One('product.uom', 'Uom', required=True,
        domain=[
            ('category', '=', Id('product', 'uom_cat_time')),
            ])
    quantity = fields.Float('Quantity', required=True, digits='uom')
    cost = fields.Function(fields.Numeric('Cost'), 'get_cost')
    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'get_company', searcher='search_company')

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
        work_center = (self.operation.work_center or
            self.operation.work_center_category)
        if not work_center:
            return Decimal('0.0')
        quantity = Uom.compute_qty(self.uom, self.quantity,
            work_center.uom)
        return Decimal(str(quantity)) * work_center.cost_price

    def get_company(self, name):
        return (self.operation.production.company.id
            if self.operation.production else None)

    @classmethod
    def search_company(cls, name, clause):
        return [('operation.production.company',) + tuple(clause[1:])]

    @fields.depends('_parent_operation.id', 'operation')
    def on_change_with_uom(self):
        if self.operation and getattr(self.operation, 'work_center', None):
            return self.operation.work_center.uom.id


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    route = fields.Many2One('production.route', 'Route',
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            })
    operations = fields.One2Many('production.operation', 'production',
        'Operations', order=[
            ('sequence', 'ASC'),
            ('id', 'ASC'),
            ], states={
            'readonly': Eval('state') == 'done',
            })

    def get_operation(self, route_operation):
        Operation = Pool().get('production.operation')
        values = Operation.default_get(
                    list(Operation._fields.keys()), with_rec_name=False)

        operation = Operation(**values)
        operation.sequence = route_operation.sequence
        operation.work_center_category = route_operation.work_center_category
        operation.work_center = route_operation.work_center
        operation.operation_type = route_operation.operation_type
        operation.route_operation = route_operation
        if hasattr(Operation, 'subcontracted_product'):
            operation.subcontracted_product = (
                route_operation.subcontracted_product)
        return operation

    @fields.depends('route', 'operations')
    def on_change_route(self):
        self.operations = None
        operations = []
        if self.route:
            for route_operation in self.route.operations:
                operation = self.get_operation(route_operation)
                operations.append(operation)
            self.operations = operations

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
        Config = pool.get('production.configuration')
        Operation = pool.get('production.operation')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Warning = pool.get('res.user.warning')

        config = Config(1)
        if config.check_state_operation:
            pending_operations = Operation.search([
                    ('production', 'in', [p.id for p in productions]),
                    ('state', 'not in', ['cancelled', 'done']),
                    ], limit=1)
            if pending_operations:
                operation, = pending_operations
                key ='pending_operation_%d' % operation.id
                if config.check_state_operation == 'user_warning':
                    if Warning.check(key):
                        raise UserWarning(key,
                            gettext('production_operation.pending_operations',
                                production=operation.production.rec_name,
                                operation=operation.rec_name))
                else:
                    raise UserError(
                        gettext('production_operation.pending_operations',
                            production=operation.production.rec_name,
                            operation=operation.rec_name))

        if hasattr(Product, 'cost_price'):
            digits = Product.cost_price.digits
        else:
            digits = Template.cost_price.digits

        for production in productions:
            operation_cost = sum(o.cost for o in production.operations)
            if operation_cost == Decimal('0.0'):
                continue
            total_quantity = Decimal(str(sum(o.quantity for o in
                        production.outputs)))
            if total_quantity:
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

    @classmethod
    def compute_request(cls, product, warehouse, quantity, date, company,
            order_point=None):
        "Inherited from stock_supply_production"
        production = super(Production, cls).compute_request(product,
            warehouse, quantity, date, company, order_point)
        if product.boms and product.boms[0].route:
            production.route = product.boms[0].route
            # TODO: it should be called next to set_moves()
            production.set_operations()
        return production

    def set_operations(self):
        if not self.route:
            return

        self.operations = tuple()
        for route_operation in self.route.operations:
            self.operations += (self._operation(route_operation), )

    def _operation(self, route_operation):
        Operation = Pool().get('production.operation')
        return Operation(
            sequence=route_operation.sequence,
            work_center_category=route_operation.work_center_category,
            work_center=route_operation.work_center,
            operation_type=route_operation.operation_type,
            route_operation=route_operation,
            )


class OperationSubcontrat(metaclass=PoolMeta):
    __name__ = 'production.operation'

    subcontracted_product = fields.Many2One('product.product',
        'Subcontracted product', domain=[('type', '=', 'service')],
        context={
            'company': Eval('company', -1),
        },
        depends={'company'})
    purchase_request = fields.Many2One('purchase.request', 'Purchase Request')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'create_purchase_request': {
                    'invisible': (~(Eval('state').in_(['planned', 'waiting'])) |
                        ~Bool(Eval('subcontracted_product',-1))),
                    'readonly': (Bool(Eval('purchase_request',-1)))
                },
            })

    def _get_purchase_request(self):
        pool = Pool()
        Request = pool.get('purchase.request')
        Uom = pool.get('product.uom')

        product = self.subcontracted_product
        uom = product.purchase_uom
        quantity = self.production and self.production.quantity
        # TODO: add uom and domain to subcontracted product?
        # quantity = Uom.compute_qty(self.production.uom, quantity, uom)
        shortage_date = self.production.planned_date
        company = self.production.company
        supplier_pattern = {}
        supplier_pattern['company'] = company.id
        supplier, purchase_date = Request.find_best_supplier(product,
            shortage_date, **supplier_pattern)


        location = self.production.warehouse
        request = Request(product=product,
            party=None,
            quantity=quantity,
            uom=uom,
            purchase_date=purchase_date,
            supply_date=shortage_date,
            company=company,
            warehouse=location.id,
            origin=self,
            )
        return request

    @classmethod
    @ModelView.button
    def create_purchase_request(cls, operations):
        to_save = []
        for operation in operations:
            if not operation.subcontracted_product:
                continue
            request = operation._get_purchase_request()
            operation.purchase_request = request
            to_save.append(operation)
        cls.save(to_save)

    def get_cost(self, name):
        cost = super().get_cost(name)
        if self.purchase_request and self.purchase_request.purchase_line:
            cost += self.purchase_request.purchase_line.amount
        return cost

    @classmethod
    def wait(cls, operations):
        pool = Pool()
        Config = pool.get('production.configuration')
        Warning = pool.get('res.user.warning')
        op_warn = []
        config = Config(1)

        if config.check_state_operation == 'user_warning':
            op_warn = [op for op in operations if op.purchase_request]
            if op_warn:
                operation, = op_warn
                key ='operation_%d' % operation.id
                if Warning.check(key):
                    raise UserWarning(key,
                        gettext('production_operation.purchase_request_wait',
                            production=operation.production.rec_name,
                            operation=operation.rec_name))

        super().wait(operations)

    @classmethod
    def done(cls, operations):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        requests = set([o.purchase_request for o in operations if
            o.purchase_request])
        purchases = [r.purchase for r in requests if r.purchase]

        for request in requests:
            if request.purchase:
                continue
            raise UserError(
                gettext('production_operation.purchase_missing',
                    request=request.rec_name))

        for purchase in purchases:
            if purchase.state in ('processing', 'done'):
                continue
            raise UserError(
                gettext('production_operation.purchase_pending',
                    purchase=purchase.rec_name))

        super().done(operations)
        if purchases:
            Purchase.process(purchases)

    @classmethod
    def copy(cls, operations, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('purchase_request', None)
        return super().copy(operations, default=default)


class PurchaseLine(metaclass=PoolMeta):
    __name__ = 'purchase.line'

    origin = fields.Reference('Origin', selection='get_origin', select=True,
        states={
            'readonly': Eval('purchase_state') != 'draft',
            },
        depends=['purchase_state'])

    def _get_invoice_line_quantity(self):
        pool = Pool()
        ProductionOperation = pool.get('production.operation')
        if not isinstance(self.origin, ProductionOperation):
            return super()._get_invoice_line_quantity()

        if not (self.purchase.invoice_method == 'shipment'
               and self.origin.state == 'done'):
            return 0
        return super()._get_invoice_line_quantity()

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        origins = [cls.__name__, 'production.operation', 'production']
        try:
            Pool().get('stock.order_point')
            origins += ['stock.order_point']
        except KeyError:
            pass
        try:
            Pool().get('purchase.request')
            origins += ['purchase.request']
        except KeyError:
            pass
        return origins

    @classmethod
    def get_origin(cls):
        IrModel = Pool().get('ir.model')
        get_name = IrModel.get_name
        models = cls._get_origin()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('origin', None)
        super().copy(lines, default=default)


class PurchaseRequest(metaclass=PoolMeta):
    __name__ = 'purchase.request'

    @classmethod
    def _get_origin(cls):
        return super()._get_origin()  | {'production.operation'}


class CreatePurchase(metaclass=PoolMeta):
    __name__ = 'purchase.request.create_purchase'

    @classmethod
    def compute_purchase_line(cls, key, requests, purchase):

        line = super().compute_purchase_line(key, requests, purchase)
        if requests:
            request = requests[0]
            line.origin = request.origin
        return line
