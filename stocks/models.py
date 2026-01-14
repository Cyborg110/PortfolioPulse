# /stocks/models.py
import asyncio
from typing import List, Dict

from t_tech.invest import CandleInterval

from base.models import BaseAsset
from stocks.database import stocks_database
from candles.models import MultiTimeframeCandles
from payments.dividends import Dividends


class Stock(BaseAsset):
    def __init__(self, identifier, identifier_type='ticker'):
        super().__init__(identifier, identifier_type)
        # Дополнительные переменные
        self.sector = None
        # Дополнительные переменные для метрик
        self.candles: [MultiTimeframeCandles, None] = None      # Свечи
        self.payments: [Dividends, None] = None                  # Дивиденды
        self._get_params()

    def _get_params(self) -> None:
        """
        Заполняет переменные класса данными из базы данных через StocksDatabase.
        :return:
        :raise: Exception: Если данные не найдены и не удалось получить из API.
        """
        # Если передан FIGI, сразу запрашиваем по нему
        record = stocks_database.get_instrument_by_identifier(self.identifier, self.identifier_type)
        if record:
            self._update_from_record(record)
        else:
            raise ValueError(f"Акция с {self.identifier_type} {self.identifier} не найдена в базе")

        self.candles = MultiTimeframeCandles(figi=self.figi)
        self.payments = Dividends(figi=self.figi, instrument_type="stock",
                                  candles=self.candles[CandleInterval.CANDLE_INTERVAL_DAY])

    def _update_from_record(self, record):
        """
        Обновляет атрибуты класса из записи базы данных.
        :param record: Объект модели Stock (из database)
        :return:
        """
        self.figi = record.figi
        self.position_uid = record.position_uid
        self.ticker = record.ticker
        self.name = record.name
        self.currency = record.currency
        self.lot = record.lot
        self.sector = record.sector
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
        Рассчитывает специфичные метрики для актива и сохраняет их как атрибуты.
        Реализуется в дочерних классах. (Payments, Candles)

        Returns:
            dict: Словарь с рассчитанными метриками.
        """
        self.candles.calculate_static()
        self.payments.calculate_metrics()

    def drop(self):
        """
        Очистка БД для актива.
        :return:
        """
        self.candles.drop()
        self.payments.drop()

    def __str__(self):
        return f"Тикер: {self.ticker}\n" \
               f"FIGI: {self.figi}\n" \
               f"Название: {self.name}\n" \
               f"{self.candles[CandleInterval.CANDLE_INTERVAL_DAY]}\n" \
               f"{self.payments}\n"


class Stocks:
    """
    Класс для массовой работы с акциями, соответствующими фильтрам.
    """

    def __init__(self, filters: Dict = None):
        """
        Инициализация объекта с акциями, отфильтрованными по заданным критериям.
        :param filters: Словарь фильтров (например, {"currency": "RUB", "for_qual_investor_flag": False}).
        """
        self.filters = filters or {}
        self.stocks: List[Stock] = []
        self._load_stocks()

    def _load_stocks(self):
        """
        Загружает акции из базы данных по заданным фильтрам и создаёт список объектов.
        """
        # Запрашиваем записи из базы данных
        stock_records = stocks_database.query_data(self.filters)
        # Создаём объекты Bond для каждого FIGI
        self.stocks = [Stock(record.figi, identifier_type='figi') for record in stock_records]

    def calculate_metrics(self):
        """
        Подсчет метрик для всех акций.
        :return:
        """
        for stock in self.stocks:
            stock.calculate_metrics()

    async def update_candles(self, sleep: float = 0):
        """
        Обновляет свечи для всех акций в списке.
        :param sleep: Время засыпания между запросами.
        """
        count = len(self.stocks)
        i = 0
        for stock in self.stocks:
            i += 1
            try:
                await stock.candles.update_candles(from_time=stock.first_1day_candle_date)
                await asyncio.sleep(sleep)
                print(f"{i}/{count} {stock.ticker} свечи обновлены!")
            except Exception as e:
                print(f"Не удалось обновить свечи для {stock.ticker}: {e}")

    async def update_payments(self, sleep: float = 0):
        """
        Обновляет свечи для всех акций в списке.
        :param sleep: Время засыпания между запросами.
        """
        count = len(self.stocks)
        i = 0
        for stock in self.stocks:
            i += 1
            try:
                await stock.payments.update_payments()
                await asyncio.sleep(sleep)
                print(f"{i}/{count} {stock.ticker} дивиденды обновлены!")
            except Exception as e:
                print(f"Не удалось обновить дивиденды для {stock.ticker}: {e}")

    def sort(self, key=None, reverse=False) -> list:
        self.stocks.sort(key=key, reverse=reverse)
        return self.stocks

    def __iter__(self):
        """
        Позволяет итерироваться по списку акций.
        """
        return iter(self.stocks)

    def __len__(self):
        return len(self.stocks)
