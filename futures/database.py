# /futures/database.py
from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer
from datetime import datetime
from base.database import BaseDatabase, Base
from api_client import tinkoff_api_client


class Future(Base):
    __tablename__ = "futures"
    figi = Column(String, primary_key=True)         # Уникальный идентификатор инструмента
    position_uid = Column(String)                   # Дополнительный идентификатор инструмента
    ticker = Column(String)                         # Тикер для поиска (например, MAU5)
    name = Column(String)                           # Название фьючерса (например, MMI-9.25 Индекс Металлов и добычи)
    currency = Column(String)                       # Валюта торгов (например, RUB)
    lot = Column(Integer)                           # Размер лота для торгов
    sector = Column(String)                         # Сектор экономики (например, SECTOR_MATERIALS)
    country_of_risk = Column(String)                # Страна риска (например, RU)
    min_price_increment = Column(Float)             # Минимальный шаг цены (например, 1.0)
    for_iis_flag = Column(Boolean)                  # Доступность для ИИС
    for_qual_investor_flag = Column(Boolean)        # Требуется статус квалифицированного инвестора
    buy_available_flag = Column(Boolean)            # Доступность для покупки
    sell_available_flag = Column(Boolean)           # Доступность для продажи
    api_trade_available_flag = Column(Boolean)      # Доступность торгов через API
    trading_status = Column(String)                 # Статус торгов (например, NORMAL_TRADING)
    first_1min_candle_date = Column(DateTime)       # Дата первой минутной свечи для исторических данных
    first_1day_candle_date = Column(DateTime)       # Дата первой дневной свечи для исторических данных
    expiration_date = Column(DateTime)              # Дата экспирации фьючерса
    asset_type = Column(String)                     # Тип базового актива (например, TYPE_INDEX)
    basic_asset = Column(String)                    # Базовый актив (например, MOEXMM)
    initial_margin_on_buy = Column(Float)           # Маржа для покупки
    initial_margin_on_sell = Column(Float)          # Маржа для продажи
    updated_at = Column(DateTime)                   # Время последнего обновления записи


class FuturesDatabase(BaseDatabase):
    def get_instrument_by_identifier(self, identifier, identifier_type):
        """
        Возвращает данные об фьючерсе по идентификатору.
        :param identifier: Значение идентификатора (FIGI или ticker).
        :param identifier_type: Тип идентификатора ('figi' или 'ticker').
        :return: Объект модели Future или None, если не найден.
        :raises Exception: Если запрос не удался.
        """
        try:
            with self.Session() as session:
                if identifier_type == 'figi':
                    return session.query(Future).filter_by(figi=identifier).first()
                elif identifier_type == 'ticker':
                    return session.query(Future).filter_by(ticker=identifier).first()
                else:
                    raise ValueError(f"Неподдерживаемый тип идентификатора: {identifier_type}")
        except Exception as e:
            raise Exception(f"Ошибка при запросе данных фьючерса по {identifier_type} {identifier}: {str(e)}")

    async def fetch_data(self):
        futures = await tinkoff_api_client.get_futures()
        with self.Session() as session:
            for future in futures:
                session.merge(Future(
                    figi=future.figi,
                    position_uid=future.position_uid,
                    ticker=future.ticker,
                    name=future.name,
                    currency=future.currency,
                    lot=future.lot,
                    sector=future.sector,
                    country_of_risk=future.country_of_risk,
                    min_price_increment=future.min_price_increment.units + future.min_price_increment.nano / 1e9,
                    for_iis_flag=future.for_iis_flag,
                    for_qual_investor_flag=future.for_qual_investor_flag,
                    buy_available_flag=future.buy_available_flag,
                    sell_available_flag=future.sell_available_flag,
                    api_trade_available_flag=future.api_trade_available_flag,
                    trading_status=future.trading_status.name,
                    first_1min_candle_date=future.first_1min_candle_date,
                    first_1day_candle_date=future.first_1day_candle_date,
                    expiration_date=future.expiration_date,
                    asset_type=future.asset_type,
                    basic_asset=future.basic_asset,
                    initial_margin_on_buy=future.initial_margin_on_buy.units + future.initial_margin_on_buy.nano / 1e9,
                    initial_margin_on_sell=future.initial_margin_on_sell.units + future.initial_margin_on_sell.nano / 1e9,
                    updated_at=datetime.now()
                ))
            session.commit()

    def query_data(self, filters):
        with self.Session() as session:
            return session.query(Future).filter_by(**filters).all()


futures_database = FuturesDatabase()
