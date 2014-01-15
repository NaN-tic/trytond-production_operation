===================
Production Scenario
===================

=============
General Setup
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install production Module::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([('name', '=', 'production_operation')])
    >>> Module.install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='Dunder Mifflin')
    >>> party.save()
    >>> company.party = party
    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> if not currencies:
    ...     currency = Currency(name='Euro', symbol=u'$', code='USD',
    ...         rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...         mon_decimal_point=',')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Configuration production location::

    >>> Location = Model.get('stock.location')
    >>> warehouse, = Location.find([('code', '=', 'WH')])
    >>> production_location, = Location.find([('code', '=', 'PROD')])
    >>> warehouse.production_location = production_location
    >>> warehouse.save()

Create a route with two operations on diferent work center::

    >>> ProductUom = Model.get('product.uom')
    >>> Route = Model.get('production.route')
    >>> OperationType = Model.get('production.operation.type')
    >>> RouteOperation = Model.get('production.route.operation')
    >>> assembly = OperationType(name='Assembly')
    >>> assembly.save()
    >>> clean = OperationType(name='clean')
    >>> clean.save()
    >>> hour, = ProductUom.find([('name', '=', 'Hour')])
    >>> WorkCenter = Model.get('production.work_center')
    >>> WorkCenterCategory = Model.get('production.work_center.category')
    >>> category = WorkCenterCategory()
    >>> category.name = 'Default Category'
    >>> category.uom = hour
    >>> category.cost_price = Decimal('25.0')
    >>> category.save()
    >>> workcenter1 = WorkCenter()
    >>> workcenter1.name = 'Assembler Machine'
    >>> workcenter1.type = 'machine'
    >>> workcenter1.category = category
    >>> workcenter1.uom == hour
    True
    >>> workcenter1.cost_price
    Decimal('25.0')
    >>> workcenter1.save()
    >>> workcenter2 = WorkCenter()
    >>> workcenter2.name = 'Cleaner Machine'
    >>> workcenter2.type = 'machine'
    >>> workcenter2.category = category
    >>> workcenter2.cost_price = Decimal('50.0')
    >>> workcenter2.save()
    >>> route = Route(name='default route')
    >>> route_operation = RouteOperation()
    >>> route.operations.append(route_operation)
    >>> route_operation.sequence = 1
    >>> route_operation.operation_type = assembly
    >>> route_operation.work_center_category = category
    >>> route_operation.work_center = workcenter1
    >>> route_operation.quantity = 1
    >>> route_operation = RouteOperation()
    >>> route.operations.append(route_operation)
    >>> route_operation.sequence = 2
    >>> route_operation.operation_type = clean
    >>> route_operation.work_center_category = category
    >>> route_operation.work_center = workcenter2
    >>> route_operation.quantity = 1
    >>> route.save()
    >>> route.reload()
    >>> len(route.operations) == 2
    True


Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal(30)
    >>> template.cost_price = Decimal(20)
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Create Components::

    >>> component1 = Product()
    >>> template1 = ProductTemplate()
    >>> template1.name = 'component 1'
    >>> template1.default_uom = unit
    >>> template1.type = 'goods'
    >>> template1.list_price = Decimal(5)
    >>> template1.cost_price = Decimal(1)
    >>> template1.save()
    >>> component1.template = template1
    >>> component1.save()

    >>> meter, = ProductUom.find([('name', '=', 'Meter')])
    >>> centimeter, = ProductUom.find([('name', '=', 'centimeter')])
    >>> component2 = Product()
    >>> template2 = ProductTemplate()
    >>> template2.name = 'component 2'
    >>> template2.default_uom = meter
    >>> template2.type = 'goods'
    >>> template2.list_price = Decimal(7)
    >>> template2.cost_price = Decimal(5)
    >>> template2.save()
    >>> component2.template = template2
    >>> component2.save()

Create Bill of Material::

    >>> BOM = Model.get('production.bom')
    >>> BOMInput = Model.get('production.bom.input')
    >>> BOMOutput = Model.get('production.bom.output')
    >>> bom = BOM(name='product')
    >>> input1 = BOMInput()
    >>> bom.inputs.append(input1)
    >>> input1.product = component1
    >>> input1.quantity = 5
    >>> input2 = BOMInput()
    >>> bom.inputs.append(input2)
    >>> input2.product = component2
    >>> input2.quantity = 150
    >>> input2.uom = centimeter
    >>> output = BOMOutput()
    >>> bom.outputs.append(output)
    >>> output.product = product
    >>> output.quantity = 1
    >>> bom.save()

    >>> ProductBom = Model.get('product.product-production.bom')
    >>> product.boms.append(ProductBom(bom=bom))
    >>> product.save()

Create an Inventory::

    >>> Inventory = Model.get('stock.inventory')
    >>> InventoryLine = Model.get('stock.inventory.line')
    >>> storage, = Location.find([
    ...         ('code', '=', 'STO'),
    ...         ])
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory_line1 = InventoryLine()
    >>> inventory.lines.append(inventory_line1)
    >>> inventory_line1.product = component1
    >>> inventory_line1.quantity = 10
    >>> inventory_line2 = InventoryLine()
    >>> inventory.lines.append(inventory_line2)
    >>> inventory_line2.product = component2
    >>> inventory_line2.quantity = 5
    >>> inventory.save()
    >>> Inventory.confirm([inventory.id], config.context)
    >>> inventory.state
    u'done'

Make a production::

    >>> Production = Model.get('production')
    >>> Operation = Model.get('production.operation')
    >>> OperationTracking = Model.get('production.operation.tracking')
    >>> production = Production()
    >>> production.product = product
    >>> production.route = route
    >>> len(production.operations) == 2
    True
    >>> [o.operation_type for o in production.operations] == [assembly, clean]
    True
    >>> production.bom = bom
    >>> production.quantity = 2
    >>> sorted([i.quantity for i in production.inputs]) == [10, 300]
    True
    >>> output, = production.outputs
    >>> output.quantity == 2
    True
    >>> production.save()
    >>> production.reload()
    >>> [o.state for o in production.operations] == ['planned', 'planned']
    True
    >>> Production.wait([production.id], config.context)
    >>> production.state
    u'waiting'
    >>> Production.assign_try([production.id], config.context)
    True
    >>> production.reload()
    >>> all(i.state == 'assigned' for i in production.inputs)
    True
    >>> Production.run([production.id], config.context)
    >>> production.reload()
    >>> all(i.state == 'done' for i in production.inputs)
    True
    >>> Production.done([production.id], config.context)
    Traceback (most recent call last):
        ...
    UserError: ('UserError', (u'Production "1" can not be done because their operation "Assembly" is not done.', ''))
    >>> operation1, operation2 = production.operations
    >>> tracking = OperationTracking()
    >>> operation1.lines.append(tracking)
    >>> minute, = ProductUom.find([('name', '=', 'Minute')])
    >>> tracking.quantity = 180.0
    >>> tracking.uom = minute
    >>> operation1.save()
    >>> new_operation = Operation()
    >>> production.operations.append(new_operation)
    >>> new_operation.work_center_category = category
    >>> new_operation.operation_type = assembly
    >>> production.save()
    >>> production.reload()
    >>> len(production.operations) == 3
    True
    >>> operations = [o.id for o in production.operations]
    >>> Operation.run(operations, config.context)
    >>> Operation.done(operations, config.context)
    >>> production.reload()
    >>> production.state
    u'done'
    >>> production.cost == Decimal('100')
    True
