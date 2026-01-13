# /options/models.py
from typing import List, Dict

from base.models import BaseAsset
from options.database import options_database


class Option(BaseAsset):
    def __init__(self, identifier, identifier_type='ticker'):
        super().__init__(identifier, identifier_type)
        # Дополнительные переменные
        self.strike_price = None
        self.expiration_date = None
        self.direction = None
        self.style = None
        self.basic_asset = None
        # Переменные для метрик
        self.delta = None
        self._get_params()

    def _get_params(self) -> None:
        """
        Заполняет переменные класса данными из базы данных через OptionsDatabase.
        :return:
        :raises Exception: Если данные не найдены.
        """
        try:
            record = options_database.get_instrument_by_identifier(self.identifier, self.identifier_type)
            if record:
                self._update_from_record(record)
            else:
                raise ValueError(f"Опцион с {self.identifier_type} {self.identifier} не найден в базе")
        except Exception as e:
            raise Exception(f"Ошибка при загрузке данных для {self.identifier}: {str(e)}")

    def _update_from_record(self, record):
        """
        Обновляет атрибуты класса из записи базы данных.
        :param record: Объект модели Option (из database).
        :return:
        """
        self.figi = None  # Опционы не имеют FIGI
        self.uid = record.uid
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
        self.strike_price = record.strike_price
        self.expiration_date = record.expiration_date
        self.direction = record.direction
        self.style = record.style
        self.basic_asset = record.basic_asset
        self.updated_at = record.updated_at

    def calculate_metrics(self):
        """
        Рассчитывает метрики для опциона и сохраняет их как атрибуты.
        Поскольку данные свечей пока не реализованы, возвращает заглушку.
        :return: Словарь с метриками или сообщение об ошибке.
        """
        try:
            self.delta = 0.0  # Заглушка
            return {"delta": self.delta, "message": "Ожидается реализация расчёта греков"}
        except Exception as e:
            return {"status": "error", "message": f"Ошибка при расчёте метрик: {str(e)}"}

    def drop(self):
        """
        Очистка БД для актива.
        :return:
        """
        pass


class Options:
    """
    Класс для массовой работы с опционами, соответствующими фильтрам.
    """

    def __init__(self, filters: Dict = None):
        """
        Инициализация объекта с опционами, отфильтрованными по заданным критериям.
        :param filters: Словарь фильтров (например, {"currency": "RUB", "for_qual_investor_flag": False}).
        """
        self.filters = filters or {}
        self.etfs: List[Option] = []
        self._load_options()

    def _load_options(self):
        """
        Загружает опционы из базы данных по заданным фильтрам и создаёт список объектов Bond.
        """
        try:
            # Запрашиваем записи из базы данных
            options_records = options_database.query_data(self.filters)
            # Создаём объекты Bond для каждого FIGI
            self.options = [Option(record.figi, identifier_type='figi') for record in options_records]
        except Exception as e:
            print(f"Ошибка при загрузке облигаций: {str(e)}")
            self.options = []

    def __iter__(self):
        """
        Позволяет итерироваться по списку облигаций.
        """
        return iter(self.options)
