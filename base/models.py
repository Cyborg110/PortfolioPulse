# /base/models.py
from abc import ABC, abstractmethod


class BaseAsset(ABC):
    def __init__(self, identifier, identifier_type='ticker'):
        """
        Инициализация объекта актива по идентификатору.

        Args:
            identifier (str): Значение идентификатора (FIGI или ticker или instrument_uid).
            identifier_type (str): Тип идентификатора ('figi' или 'ticker' или 'instrument_uid'). По умолчанию 'ticker'.
        """
        self.identifier = identifier.upper()
        self.identifier_type = identifier_type.lower()
        if self.identifier_type not in ['figi', 'ticker', 'uid']:
            raise ValueError("identifier_type must be 'figi', 'ticker', or 'uid'")

        # Общие переменные для всех типов активов
        self.position_uid = None
        self.figi = None  # Для опционов None
        self.ticker = None
        self.name = None
        self.currency = None
        self.lot = None
        self.country_of_risk = None
        self.min_price_increment = None
        self.for_iis_flag = None
        self.for_qual_investor_flag = None
        self.buy_available_flag = None
        self.sell_available_flag = None
        self.api_trade_available_flag = None
        self.trading_status = None
        self.first_1min_candle_date = None
        self.first_1day_candle_date = None
        self.updated_at = None

    @abstractmethod
    def _get_params(self):
        """
        Заполняет переменные класса данными из базы данных по идентификатору.
        Реализуется в дочерних классах для обращения к соответствующей таблице.
        """
        pass

    @abstractmethod
    def calculate_metrics(self):
        """
        Рассчитывает специфичные метрики для актива и сохраняет их как атрибуты.
        Реализуется в дочерних классах.

        Returns:
            dict: Словарь с рассчитанными метриками.
        """
        pass
