from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['Configuration']


class Configuration(metaclass=PoolMeta):
    __name__ = 'production.configuration'
    check_state_operation = fields.Selection([
            (None, ''),
            ('user_warning', 'User Warning'),
            ('user_error', 'User Error'),
            ], 'Check State Operation',
        help='Check state operation when done a production')
    allow_done_production = fields.Boolean('Allow Done Produciton',
        help='Allow done the productoin when finish the last operation')

    @staticmethod
    def default_check_state_operation():
        return 'user_error'

    @staticmethod
    def default_allow_done_production():
        return True
