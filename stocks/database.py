# /stocks/database.py
from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer
from datetime import datetime
from base.database import BaseDatabase, Base
from api_client import tinkoff_api_client


class Stock(Base):
    __tablename__ = "stocks"
    figi = Column(String, primary_key=True)         # Уникальный идентификатор инструмента
    position_uid = Column(String)                   # Дополнительный идентификатор инструмента
    ticker = Column(String)                         # Тикер для поиска (например, SBER)
    name = Column(String)                           # Название компании (например, Сбербанк)
    currency = Column(String)                       # Валюта торгов (например, RUB, USD)
    lot = Column(Integer)                           # Размер лота для торгов
    sector = Column(String)                         # Сектор экономики (например, financial)
    country_of_risk = Column(String)                # Страна риска (например, RU, US)
    min_price_increment = Column(Float)             # Минимальный шаг цены (например, 0.01)
    for_iis_flag = Column(Boolean)                  # Доступность для ИИС (индивидуальный инвестиционный счёт)
    for_qual_investor_flag = Column(Boolean)        # Требуется статус квалифицированного инвестора
    buy_available_flag = Column(Boolean)            # Доступность для покупки
    sell_available_flag = Column(Boolean)           # Доступность для продажи
    api_trade_available_flag = Column(Boolean)      # Доступность торгов через API
    trading_status = Column(String)                 # Статус торгов (например, NORMAL_TRADING)
    first_1min_candle_date = Column(DateTime)       # Дата первой минутной свечи для исторических данных
    first_1day_candle_date = Column(DateTime)       # Дата первой дневной свечи для исторических данных
    updated_at = Column(DateTime)                   # Время последнего обновления записи


class StocksDatabase(BaseDatabase):
    def get_instrument_by_identifier(self, identifier, identifier_type):
        """
        Возвращает данные об акции по идентификатору.
        :param identifier: Значение идентификатора (FIGI или ticker).
        :param identifier_type: Тип идентификатора ('figi' или 'ticker').
        :return: Объект модели Stock или None, если не найден.
        :raises Exception: Если запрос не удался.
        """
        try:
            with self.Session() as session:
                if identifier_type == 'figi':
                    return session.query(Stock).filter_by(figi=identifier).first()
                elif identifier_type == 'ticker':
                    return session.query(Stock).filter_by(ticker=identifier).first()
                else:
                    raise ValueError(f"Неподдерживаемый тип идентификатора: {identifier_type}")
        except Exception as e:
            raise Exception(f"Ошибка при запросе данных акции по {identifier_type} {identifier}: {str(e)}")

    async def fetch_data(self):
        shares = await tinkoff_api_client.get_shares()
        with self.Session() as session:
            for share in shares:
                session.merge(Stock(
                    figi=share.figi,
                    position_uid=share.position_uid,
                    ticker=share.ticker,
                    name=share.name,
                    currency=share.currency,
                    lot=share.lot,
                    sector=share.sector,
                    country_of_risk=share.country_of_risk,
                    min_price_increment=share.min_price_increment.units + share.min_price_increment.nano / 1e9,
                    for_iis_flag=share.for_iis_flag,
                    for_qual_investor_flag=share.for_qual_investor_flag,
                    buy_available_flag=share.buy_available_flag,
                    sell_available_flag=share.sell_available_flag,
                    api_trade_available_flag=share.api_trade_available_flag,
                    trading_status=share.trading_status.name,
                    first_1min_candle_date=share.first_1min_candle_date,
                    first_1day_candle_date=share.first_1day_candle_date,
                    updated_at=datetime.now()
                ))
            session.commit()

    def query_data(self, filters):
        with self.Session() as session:
            return session.query(Stock).filter_by(**filters).all()


stocks_database = StocksDatabase()
