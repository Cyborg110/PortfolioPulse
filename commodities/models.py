# /commodities/models.py
import asyncio
from typing import List, Dict

from tinkoff.invest import CandleInterval

from base.models import BaseAsset
from commodities.database import commodities_database
from candles.models import MultiTimeframeCandles


class Commodity(BaseAsset):
    def __init__(self, identifier, identifier_type='ticker'):
        super().__init__(identifier, identifier_type)
        # Дополнительные переменные для метрик
        self.candles: [MultiTimeframeCandles, None] = None
        self._get_params()

    def _get_params(self) -> None:
        """
        Заполняет переменные класса данными из базы данных через CommoditiesDatabase.
        :return:
        :raises Exception: Если данные не найдены.
        """
        record = commodities_database.get_instrument_by_identifier(self.identifier, self.identifier_type)
        if record:
            self._update_from_record(record)
        else:
            raise ValueError(f"Актив с {self.identifier_type} {self.identifier} не найден в базе")

        self.candles = MultiTimeframeCandles(figi=self.figi)

    def _update_from_record(self, record):
        """
        Обновляет атрибуты класса из записи базы данных.
        :param record: Объект модели Commodity (из database).
        :return:
        """
        self.figi = record.figi
        self.ticker = record.ticker
        self.uid = record.uid
        self.name = record.name
        self.lot = record.lot
        self.instrument_type = record.instrument_type
        self.first_1min_candle_date = record.first_1min_candle_date
        self.first_1day_candle_date = record.first_1day_candle_date
        self.updated_at = record.updated_at

    def calculate_metrics(self):
        """
        Рассчитывает метрики для индекса или сырьевого актива (например, волатильность).
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


class Commodities:
    """
    Класс для массовой работы с индексами, соответствующими фильтрам.
    """

    def __init__(self, filters: Dict = None):
        """
        Инициализация объекта с индексами, отфильтрованными по заданным критериям.
        :param filters: Словарь фильтров (например, {"currency": "RUB", "for_qual_investor_flag": False}).
        """
        self.filters = filters or {}
        self.commodities: List[Commodity] = []
        self._load_commodities()

    def _load_commodities(self):
        """
        Загружает индексы из базы данных по заданным фильтрам и создаёт список объектов Bond.
        """
        # Запрашиваем записи из базы данных
        commodities_records = commodities_database.query_data(self.filters)
        # Создаём объекты Bond для каждого FIGI
        self.commodities = [Commodity(record.figi, identifier_type='figi') for record in commodities_records]

    async def update_candles(self, sleep: float = 0):
        """
        Обновляет свечи для всех etf в списке.
        :param sleep: Время засыпания между запросами.
        """
        count = len(self.commodities)
        i = 0
        for commodity in self.commodities:
            try:
                await commodity.candles.update_candles(from_time=commodity.first_1day_candle_date)
                await asyncio.sleep(sleep)
                i += 1
                print(f"{i}/{count} {commodity.ticker} свечи обновлены!")
            except Exception as e:
                print(f"Не удалось обновить для {commodity.ticker}: {e}")

    def __iter__(self):
        """
        Позволяет итерироваться по списку индексов.
        """
        return iter(self.commodities)
