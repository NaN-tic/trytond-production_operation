import unittest
from decimal import Decimal

from proteus import Model
from trytond.exceptions import UserError
from trytond.modules.company.tests.tools import create_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Install production_operation Module
        config = activate_modules(['production_operation', 'purchase_request'])

        # Create company
        _ = create_company()

        # Configuration production location
        Location = Model.get('stock.location')
        warehouse, = Location.find([('code', '=', 'WH')])
        production_location, = Location.find([('code', '=', 'PROD')])
        warehouse.production_location = production_location
        warehouse.save()

        # Create a route with two operations on diferent work center
        ProductUom = Model.get('product.uom')
        Route = Model.get('production.route')
        OperationType = Model.get('production.operation.type')
        RouteOperation = Model.get('production.route.operation')
        assembly = OperationType(name='Assembly')
        assembly.save()
        cleaning = OperationType(name='Cleaning')
        cleaning.save()
        hour, = ProductUom.find([('name', '=', 'Hour')])
        unit, = ProductUom.find([('name', '=', 'Unit')])
        WorkCenter = Model.get('production.work_center')
        WorkCenterCategory = Model.get('production.work_center.category')
        category = WorkCenterCategory()
        category.name = 'Default Category'
        category.uom = hour
        category.cost_price = Decimal('25.0')
        category.save()
        workcenter1 = WorkCenter()
        workcenter1.name = 'Assembler Machine'
        workcenter1.type = 'machine'
        workcenter1.category = category
        self.assertEqual(workcenter1.uom, hour)
        self.assertEqual(workcenter1.cost_price, Decimal('25.0'))
        workcenter1.save()
        workcenter2 = WorkCenter()
        workcenter2.name = 'Cleaner Machine'
        workcenter2.type = 'machine'
        workcenter2.category = category
        workcenter2.cost_price = Decimal('50.0')
        workcenter2.save()
        route = Route(name='default route')
        route.uom = unit
        route_operation = RouteOperation()
        route_operation = route.operations.new()
        route_operation.sequence = 1
        route_operation.operation_type = assembly
        route_operation.work_center_category = category
        route_operation.work_center = workcenter1
        route_operation.time = 1
        route_operation.quantity = 3
        route_operation.quantity_uom = unit
        route_operation = RouteOperation()
        route_operation = route.operations.new()
        route_operation.sequence = 2
        route_operation.operation_type = cleaning
        route_operation.calculation = 'fixed'
        route_operation.work_center_category = category
        route_operation.work_center = workcenter2
        route_operation.time = 1
        route.save()
        route.reload()
        self.assertEqual(len(route.operations), 2)

        # Create product
        ProductTemplate = Model.get('product.template')
        Product = Model.get('product.product')
        product = Product()
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'goods'
        template.producible = True
        template.list_price = Decimal(30)
        template.save()
        product.template = template
        product.cost_price = Decimal(20)
        product.save()

        # Create Components
        component1 = Product()
        template1 = ProductTemplate()
        template1.name = 'component 1'
        template1.default_uom = unit
        template1.type = 'goods'
        template1.list_price = Decimal(5)
        template1.save()
        component1.template = template1
        component1.cost_price = Decimal(1)
        component1.save()
        meter, = ProductUom.find([('name', '=', 'Meter')])
        centimeter, = ProductUom.find([('symbol', '=', 'cm')])
        component2 = Product()
        template2 = ProductTemplate()
        template2.name = 'component 2'
        template2.default_uom = meter
        template2.type = 'goods'
        template2.list_price = Decimal(7)
        template2.save()
        component2.template = template2
        component2.cost_price = Decimal(5)
        component2.save()

        # Create Bill of Material
        BOM = Model.get('production.bom')
        BOMOutput = Model.get('production.bom.output')
        bom = BOM(name='product')
        input1 = bom.inputs.new()
        input1.product = component1
        input1.quantity = 5
        input2 = bom.inputs.new()
        input2.product = component2
        input2.quantity = 150
        input2.unit = centimeter
        output = BOMOutput()
        output = bom.outputs.new()
        output.product = product
        output.quantity = 1
        bom.save()
        ProductBom = Model.get('product.product-production.bom')
        product.boms.append(ProductBom(bom=bom))
        product.save()

        # Create an Inventory
        Inventory = Model.get('stock.inventory')
        InventoryLine = Model.get('stock.inventory.line')
        storage, = Location.find([
            ('code', '=', 'STO'),
        ])
        inventory = Inventory()
        inventory.location = storage
        inventory_line1 = InventoryLine()
        inventory.lines.append(inventory_line1)
        inventory_line1.product = component1
        inventory_line1.quantity = 10
        inventory_line2 = InventoryLine()
        inventory.lines.append(inventory_line2)
        inventory_line2.product = component2
        inventory_line2.quantity = 5
        inventory.save()
        Inventory.confirm([inventory.id], config.context)
        self.assertEqual(inventory.state, 'done')

        # Make a production
        Production = Model.get('production')
        Operation = Model.get('production.operation')
        OperationTracking = Model.get('production.operation.tracking')
        production = Production()
        production.product = product
        production.route = route
        self.assertEqual(len(production.operations), 2)
        self.assertEqual([o.operation_type for o in production.operations
                          ], [assembly, cleaning])
        production.bom = bom
        production.quantity = 2
        self.assertEqual(
            sorted([i.quantity for i in production.inputs]), [10, 300])
        output, = production.outputs
        self.assertEqual(output.quantity, 2)
        production.save()
        production.reload()
        self.assertEqual([o.state for o in production.operations
                          ], ['planned', 'planned'])
        Production.wait([production.id], config.context)
        self.assertEqual(production.state, 'waiting')
        Production.assign_try([production.id], config.context)
        production.reload()
        self.assertEqual(all(i.state == 'assigned' for i in production.inputs),
                         True)
        Production.run([production.id], config.context)
        production.reload()
        self.assertEqual(all(i.state == 'done' for i in production.inputs),
                         True)
        self.assertEqual(
            all(o.state == 'waiting' for o in production.operations), True)
        with self.assertRaises(UserError):

            Production.do([production.id], config.context)
        operation1, operation2 = production.operations
        tracking = OperationTracking()
        tracking = operation1.lines.new()
        minute, = ProductUom.find([('name', '=', 'Minute')])
        tracking.quantity = 180.0
        tracking.uom = minute
        operation1.save()
        new_operation = production.operations.new()
        new_operation.work_center_category = category
        new_operation.operation_type = assembly
        production.save()
        production.reload()
        self.assertEqual(len(production.operations), 3)
        operations = [o.id for o in production.operations]
        Operation.run(operations, config.context)
        Operation.done(operations, config.context)
        production.reload()
        self.assertEqual(production.state, 'done')
        self.assertEqual(production.cost, Decimal('100.0000'))

        # Check production is not done on last operation done
        Production = Model.get('production')
        Operation = Model.get('production.operation')
        ProductionConfiguration = Model.get('production.configuration')
        production_configuration = ProductionConfiguration(1)
        production_configuration.allow_done_production = False
        production_configuration.save()
        production = Production()
        production.product = product
        production.route = route
        production.bom = bom
        production.quantity = 2
        production.save()
        production.reload()
        Production.wait([production.id], config.context)
        Production.run([production.id], config.context)
        production.reload()
        operations = [o.id for o in production.operations]
        Operation.run(operations, config.context)
        Operation.done(operations, config.context)
        production.reload()
        self.assertEqual(production.state, 'waiting')
