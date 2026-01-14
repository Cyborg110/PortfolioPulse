# /futures/models.py
import asyncio
from typing import List, Dict

from t_tech.invest import CandleInterval

from base.models import BaseAsset
from futures.database import futures_database
from candles.models import MultiTimeframeCandles


class Future(BaseAsset):
    def __init__(self, identifier, identifier_type='ticker'):
        super().__init__(identifier, identifier_type)
        # Дополнительные переменные
        self.sector = None
        # Дополнительные переменные для метрик
        self.candles: [MultiTimeframeCandles, None] = None
        self._get_params()

    def _get_params(self) -> None:
        """
        Заполняет переменные класса данными из базы данных через FuturesDatabase.
        :return:
        :raises Exception: Если данные не найдены.
        """
        record = futures_database.get_instrument_by_identifier(self.identifier, self.identifier_type)
        if record:
            self._update_from_record(record)
        else:
            raise ValueError(f"Фьючерс с {self.identifier_type} {self.identifier} не найден в базе")

        self.candles = MultiTimeframeCandles(figi=self.figi)

    def _update_from_record(self, record):
        """
        Обновляет атрибуты класса из записи базы данных.
        :param record: Объект модели Future (из database).
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
        Реализуется в дочерних классах.

        Returns:
            dict: Словарь с рассчитанными метриками.
        """
        pass

    def drop(self):
        """
        Очистка БД для актива.
        :return:
        """
        self.candles.drop()


class Futures:
    """
    Класс для массовой работы с фьючерсами, соответствующими фильтрам.
    """

    def __init__(self, filters: Dict = None):
        """
        Инициализация объекта с фьючерсами, отфильтрованными по заданным критериям.
        :param filters: Словарь фильтров (например, {"currency": "RUB", "for_qual_investor_flag": False}).
        """
        self.filters = filters or {}
        self.futures: List[Future] = []
        self._load_filters()

    def _load_filters(self):
        """
        Загружает фьючерсы из базы данных по заданным фильтрам и создаёт список объектов.
        """
        # Запрашиваем записи из базы данных
        futures_records = futures_database.query_data(self.filters)
        # Создаём объекты Bond для каждого FIGI
        self.futures = [Future(record.figi, identifier_type='figi') for record in futures_records]

    async def update_candles(self, interval: CandleInterval, sleep: float = 0):
        """
        Обновляет свечи для всех фьючерсов в списке.
        :param interval: Интервал свечи (опционально). Если None, обновляет все интервалы.
        :param sleep: Время засыпания между запросами.
        """
        count = len(self.futures)
        i = 0
        for future in self.futures:
            try:
                await future.candles[interval].update_candles(from_time=future.first_1day_candle_date)
                await asyncio.sleep(sleep)
                print(f"{i}/{count} {future.ticker} свечи обновлены!")
            except Exception as e:
                print(f"Не удалось обновить для {future.ticker}: {e}")

    def __iter__(self):
        """
        Позволяет итерироваться по списку фьючерсов.
        """
        return iter(self.futures)
