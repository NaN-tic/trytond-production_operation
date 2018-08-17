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

    @staticmethod
    def default_check_state_operation():
        return 'user_error'
