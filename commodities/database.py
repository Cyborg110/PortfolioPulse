# /commodities/database.py
from sqlalchemy import Column, String, DateTime, Integer
from datetime import datetime
from base.database import BaseDatabase, Base
from api_client import tinkoff_api_client


class Commodity(Base):
    __tablename__ = "commodities"
    figi = Column(String, primary_key=True)         # Уникальный идентификатор инструмента
    ticker = Column(String, index=True)             # Тикер для поиска (например, LCOc1)
    uid = Column(String, index=True)                # Уникальный идентификатор (instrument_uid)
    name = Column(String)                           # Название (например, Нефть Brent)
    lot = Column(Integer)                           # Размер лота (0 для индексов/сырья)
    instrument_type = Column(String)                # Тип инструмента (например, commodity)
    first_1min_candle_date = Column(DateTime)       # Дата первой минутной свечи
    first_1day_candle_date = Column(DateTime)       # Дата первой дневной свечи
    updated_at = Column(DateTime)                   # Время последнего обновления записи


class CommoditiesDatabase(BaseDatabase):
    def get_instrument_by_identifier(self, identifier, identifier_type):
        """
        Возвращает данные об активе по идентификатору.
        :param identifier: Значение идентификатора (FIGI, ticker или uid).
        :param identifier_type: Тип идентификатора ('figi', 'ticker', 'uid').
        :return: Объект модели Commodity или None, если не найден.
        :raises Exception: Если запрос не удался.
        """
        try:
            with self.Session() as session:
                if identifier_type == 'figi':
                    return session.query(Commodity).filter_by(figi=identifier).first()
                elif identifier_type == 'ticker':
                    return session.query(Commodity).filter_by(ticker=identifier).first()
                elif identifier_type == 'uid':
                    return session.query(Commodity).filter_by(uid=identifier).first()
                else:
                    raise ValueError(f"Неподдерживаемый тип идентификатора: {identifier_type}")
        except Exception as e:
            raise Exception(f"Ошибка при запросе данных актива по {identifier_type} {identifier}: {str(e)}")

    async def fetch_data(self):
        """
        Получает данные об индексах и сырьевых активах из API и сохраняет в БД.
        Использует find_instrument с ключевыми словами.
        """
        instruments = await tinkoff_api_client.get_commodity()
        with self.Session() as session:
            for instr in instruments:
                session.merge(Commodity(
                    figi=instr.figi,
                    ticker=instr.ticker,
                    uid=instr.uid,
                    name=instr.name,
                    lot=instr.lot,
                    instrument_type=instr.instrument_type,
                    first_1min_candle_date=instr.first_1min_candle_date,
                    first_1day_candle_date=instr.first_1day_candle_date,
                    updated_at=datetime.now()
                ))
            session.commit()

    def query_data(self, filters):
        """
        Запрашивает данные из БД с фильтрами.
        :param filters: Словарь с фильтрами (например, {'ticker': 'LCOc1'}).
        :return: Список объектов модели Commodity.
        """
        try:
            with self.Session() as session:
                return session.query(Commodity).filter_by(**filters).all()
        except Exception as e:
            raise Exception(f"Ошибка при запросе данных: {str(e)}")


commodities_database = CommoditiesDatabase()
