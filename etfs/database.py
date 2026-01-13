# /etfs/database.py
from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer
from datetime import datetime
from base.database import BaseDatabase, Base
from api_client import tinkoff_api_client


class Etf(Base):
    __tablename__ = "etfs"
    figi = Column(String, primary_key=True)         # Уникальный идентификатор инструмента
    position_uid = Column(String)                   # Дополнительный идентификатор инструмента
    ticker = Column(String)                         # Тикер для поиска (например, SOXS)
    name = Column(String)                           # Название ETF (например, Direxion Daily Semiconductors Bear 3x Shares)
    currency = Column(String)                       # Валюта торгов (например, USD)
    lot = Column(Integer)                           # Размер лота для торгов
    sector = Column(String)                         # Сектор экономики (например, equity)
    country_of_risk = Column(String)                # Страна риска (например, US)
    min_price_increment = Column(Float)             # Минимальный шаг цены (например, 0.01)
    for_iis_flag = Column(Boolean)                  # Доступность для ИИС
    for_qual_investor_flag = Column(Boolean)        # Требуется статус квалифицированного инвестора
    buy_available_flag = Column(Boolean)            # Доступность для покупки
    sell_available_flag = Column(Boolean)           # Доступность для продажи
    api_trade_available_flag = Column(Boolean)      # Доступность торгов через API
    trading_status = Column(String)                 # Статус торгов (например, NOT_AVAILABLE_FOR_TRADING)
    first_1min_candle_date = Column(DateTime)       # Дата первой минутной свечи для исторических данных
    first_1day_candle_date = Column(DateTime)       # Дата первой дневной свечи для исторических данных
    updated_at = Column(DateTime)                   # Время последнего обновления записи


class EtfsDatabase(BaseDatabase):
    def get_instrument_by_identifier(self, identifier, identifier_type):
        """
        Возвращает данные об etf по идентификатору.
        :param identifier: Значение идентификатора (FIGI или ticker).
        :param identifier_type: Тип идентификатора ('figi' или 'ticker').
        :return: Объект модели Etf или None, если не найден.
        :raises Exception: Если запрос не удался.
        """
        try:
            with self.Session() as session:
                if identifier_type == 'figi':
                    return session.query(Etf).filter_by(figi=identifier).first()
                elif identifier_type == 'ticker':
                    return session.query(Etf).filter_by(ticker=identifier).first()
                else:
                    raise ValueError(f"Неподдерживаемый тип идентификатора: {identifier_type}")
        except Exception as e:
            raise Exception(f"Ошибка при запросе данных etf по {identifier_type} {identifier}: {str(e)}")

    async def fetch_data(self):
        etfs = await tinkoff_api_client.get_etfs()
        with self.Session() as session:
            for etf in etfs:
                session.merge(Etf(
                    figi=etf.figi,
                    position_uid=etf.position_uid,
                    ticker=etf.ticker,
                    name=etf.name,
                    currency=etf.currency,
                    lot=etf.lot,
                    sector=etf.sector,
                    country_of_risk=etf.country_of_risk,
                    min_price_increment=etf.min_price_increment.units + etf.min_price_increment.nano / 1e9,
                    for_iis_flag=etf.for_iis_flag,
                    for_qual_investor_flag=etf.for_qual_investor_flag,
                    buy_available_flag=etf.buy_available_flag,
                    sell_available_flag=etf.sell_available_flag,
                    api_trade_available_flag=etf.api_trade_available_flag,
                    trading_status=etf.trading_status.name,
                    first_1min_candle_date=etf.first_1min_candle_date,
                    first_1day_candle_date=etf.first_1day_candle_date,
                    updated_at=datetime.now()
                ))
            session.commit()

    def query_data(self, filters):
        with self.Session() as session:
            return session.query(Etf).filter_by(**filters).all()


etfs_database = EtfsDatabase()
