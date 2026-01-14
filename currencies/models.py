# /currencies/models.py
import asyncio
from typing import List, Dict

from t_tech.invest import CandleInterval

from base.models import BaseAsset
from currencies.database import currencies_database
from candles.models import MultiTimeframeCandles


class Currency(BaseAsset):
    def __init__(self, identifier, identifier_type='ticker'):
        super().__init__(identifier, identifier_type)
        # Дополнительные переменные для метрик
        self.candles: [MultiTimeframeCandles, None] = None
        self._get_params()

    def _get_params(self) -> None:
        """
        Заполняет переменные класса данными из базы данных через CurrenciesDatabase.
        :return:
        :raises Exception: Если данные не найдены.
        """
        record = currencies_database.get_instrument_by_identifier(self.identifier, self.identifier_type)
        if record:
            self._update_from_record(record)
        else:
            raise ValueError(f"Валюта с {self.identifier_type} {self.identifier} не найдена в базе")

        self.candles = MultiTimeframeCandles(figi=self.figi)

    def _update_from_record(self, record):
        """
        Обновляет атрибуты класса из записи базы данных.
        :param record: Объект модели Currency (из database).
        :return:
        """
        self.figi = record.figi
        self.position_uid = record.position_uid
        self.ticker = record.ticker
        self.name = record.name
        self.currency = record.currency
        self.lot = record.lot
        self.country_of_risk = record.country_of_risk
        self.min_price_increment = record.min_price_increment
        self.for_iis_flag = record.for_iis_flag
        self.for_qual_investor_flag = record.for_qual_investor_flag
        self.buy_available_flag = record.buy_available_flag
        self.sell_available_flag = record.sell_available_flag
        self.api_trade_available_flag = record.api_trade_available_flag
        self.trading_status = record.trading_status
        self.first_1min_candle_date = record.first_1min_candle_date
        self.first_1day_candle_date = record.first_1day_candle_date
        self.updated_at = record.updated_at

    def calculate_metrics(self):
        """
        Рассчитывает метрики для валюты и сохраняет их как атрибуты.
        Поскольку данные свечей пока не реализованы, возвращает заглушку.
        :return: Словарь с метриками или сообщение об ошибке.
        """
        pass

    def drop(self):
        """
        Очистка БД для актива.
        :return:
        """
        self.candles.drop()


class Currencies:
    """
    Класс для массовой работы с валютами, соответствующими фильтрам.
    """

    def __init__(self, filters: Dict = None):
        """
        Инициализация объекта с валютами, отфильтрованными по заданным критериям.
        :param filters: Словарь фильтров (например, {"currency": "RUB", "for_qual_investor_flag": False}).
        """
        self.filters = filters or {}
        self.currencies: List[Currency] = []
        self._load_currencies()

    def _load_currencies(self):
        """
        Загружает валюты из базы данных по заданным фильтрам и создаёт список объектов.
        """
        # Запрашиваем записи из базы данных
        currencies_records = currencies_database.query_data(self.filters)
        # Создаём объекты Bond для каждого FIGI
        self.currencies = [Currency(record.figi, identifier_type='figi') for record in currencies_records]

    async def update_candles(self, sleep: float = 0):
        """
        Обновляет свечи для всех валют в списке.
        :param sleep: Время засыпания между запросами.
        """
        count = len(self.currencies)
        i = 0
        for currency in self.currencies:
            try:
                i += 1
                await currency.candles.update_candles(from_time=currency.first_1day_candle_date)
                await asyncio.sleep(sleep)
                print(f"{i}/{count} {currency.ticker} свечи обновлены!")
            except Exception as e:
                print(f"Не удалось обновить для {currency.ticker}: {e}")

    def sort(self, key=None, reverse=False) -> list:
        self.currencies.sort(key=key, reverse=reverse)
        return self.currencies

    def __iter__(self):
        """
        Позволяет итерироваться по списку валют.
        """
        return iter(self.currencies)

    def __len__(self):
        return len(self.currencies)
