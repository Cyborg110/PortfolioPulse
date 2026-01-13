# /base/database.py
from abc import ABC, abstractmethod
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path

Base = declarative_base()           # Базовый класс для БД активов
BaseCandle = declarative_base()     # Базовый класс для свечек
BasePayment = declarative_base()    # Базовый класс для выплат
BaseMetrics = declarative_base()    # Базовый класс для метрик акций


class BaseDatabase(ABC):
    # Глобальное подключение к базе данных
    base_dir = Path(__file__).resolve().parent.parent
    db_path = f"sqlite:///{base_dir}/market_data.db"
    engine = create_engine(db_path, echo=False)
    Session = sessionmaker(bind=engine)

    def __init__(self):
        # Создание таблиц при первом создании экземпляра
        Base.metadata.create_all(self.engine)

    @abstractmethod
    def get_instrument_by_identifier(self, identifier, identifier_type):
        """
        Возвращает данные об активе по идентификатору.
        :param identifier: Значение идентификатора (FIGI, ticker или instrument_uid).
        :param identifier_type: Тип идентификатора ('figi', 'ticker', 'uid').
        :return: Объект модели (например, Stock) или None, если не найден.
        :raises Exception: Если запрос не удался.
        """
        pass

    @abstractmethod
    async def fetch_data(self):
        """Получение данных из Tinkoff API и сохранение в БД."""
        pass

    @abstractmethod
    def query_data(self, filters):
        """Запрос данных из БД с фильтрами."""
        pass


class BaseCandlesDatabase(ABC):
    # Глобальное подключение к базе данных
    base_dir = Path(__file__).resolve().parent.parent
    db_path = f"sqlite:///{base_dir}/candle_data.db"
    engine = create_engine(db_path, echo=False)
    Session = sessionmaker(bind=engine)

    def __init__(self):
        # Создание таблиц при первом создании экземпляра
        BaseCandle.metadata.create_all(self.engine)


class BasePaymentsDatabase(ABC):
    # Глобальное подключение к базе данных
    base_dir = Path(__file__).resolve().parent.parent
    db_path = f"sqlite:///{base_dir}/payments.db"
    engine = create_engine(db_path, echo=False)
    Session = sessionmaker(bind=engine)

    def __init__(self):
        # Создание таблиц при первом создании экземпляра
        BasePayment.metadata.create_all(self.engine)


class BaseMetricsDatabase(ABC):
    # Глобальное подключение к базе данных
    base_dir = Path(__file__).resolve().parent.parent
    db_path = f"sqlite:///{base_dir}/metrics.db"
    engine = create_engine(db_path, echo=False)
    Session = sessionmaker(bind=engine)

    def __init__(self):
        # Создание таблиц при первом создании экземпляра
        BasePayment.metadata.create_all(self.engine)
