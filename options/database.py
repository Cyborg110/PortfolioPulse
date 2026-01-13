# /options/database.py
from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer
from datetime import datetime
from base.database import BaseDatabase, Base
from api_client import tinkoff_api_client


class Option(Base):
    __tablename__ = "options"
    uid = Column(String, primary_key=True)                  # Уникальный идентификатор инструмента
    position_uid = Column(String)                           # Дополнительный идентификатор инструмента
    ticker = Column(String)                                 # Тикер для поиска (например, VK180CL8)
    name = Column(String)                                   # Название опциона (например, ВК CALL 180₽ 20.12)
    currency = Column(String)                               # Валюта торгов (например, RUB)
    lot = Column(Integer)                                   # Размер лота для торгов
    sector = Column(String)                                 # Сектор экономики (например, SECTOR_IT)
    country_of_risk = Column(String)                        # Страна риска (например, RU)
    min_price_increment = Column(Float)                     # Минимальный шаг цены (например, 0.01)
    for_iis_flag = Column(Boolean)                          # Доступность для ИИС
    for_qual_investor_flag = Column(Boolean)                # Требуется статус квалифицированного инвестора
    buy_available_flag = Column(Boolean)                    # Доступность для покупки
    sell_available_flag = Column(Boolean)                   # Доступность для продажи
    api_trade_available_flag = Column(Boolean)              # Доступность торгов через API
    trading_status = Column(String)                         # Статус торгов (например, NORMAL_TRADING)
    first_1min_candle_date = Column(DateTime)               # Дата первой минутной свечи для исторических данных
    first_1day_candle_date = Column(DateTime)               # Дата первой дневной свечи для исторических данных
    strike_price = Column(Float)                            # Цена исполнения опциона (например, 180 RUB)
    expiration_date = Column(DateTime)                      # Дата экспирации опциона
    direction = Column(String)                              # Тип опциона (call или put)
    style = Column(String)                                  # Стиль опциона (европейский или американский)
    basic_asset = Column(String)                            # Базовый актив (например, VKCO)
    updated_at = Column(DateTime)                           # Время последнего обновления записи


class OptionsDatabase(BaseDatabase):
    def get_instrument_by_identifier(self, identifier, identifier_type):
        """
        Возвращает данные об опционе по идентификатору.
        :param identifier: Значение идентификатора (instrument_uid или ticker).
        :param identifier_type: Тип идентификатора ('instrument_uid' или 'ticker').
        :return: Объект модели Option или None, если не найден.
        :raises Exception: Если запрос не удался.
        """
        try:
            with self.Session() as session:
                if identifier_type == 'uid':
                    return session.query(Option).filter_by(uid=identifier).first()
                elif identifier_type == 'ticker':
                    return session.query(Option).filter_by(ticker=identifier).first()
                else:
                    raise ValueError(f"Неподдерживаемый тип идентификатора: {identifier_type}")
        except Exception as e:
            raise Exception(f"Ошибка при запросе данных опциона по {identifier_type} {identifier}: {str(e)}")

    async def fetch_data(self):
        options = await tinkoff_api_client.get_options()
        with self.Session() as session:
            for option in options:
                session.merge(Option(
                    uid=option.uid,
                    position_uid=option.position_uid,
                    ticker=option.ticker,
                    name=option.name,
                    currency=option.currency,
                    lot=option.lot,
                    sector=option.sector,
                    country_of_risk=option.country_of_risk,
                    min_price_increment=option.min_price_increment.units + option.min_price_increment.nano / 1e9,
                    for_iis_flag=option.for_iis_flag,
                    for_qual_investor_flag=option.for_qual_investor_flag,
                    buy_available_flag=option.buy_available_flag,
                    sell_available_flag=option.sell_available_flag,
                    api_trade_available_flag=option.api_trade_available_flag,
                    trading_status=option.trading_status.name,
                    first_1min_candle_date=option.first_1min_candle_date,
                    first_1day_candle_date=option.first_1day_candle_date,
                    strike_price=option.strike_price.units + option.strike_price.nano / 1e9,
                    expiration_date=option.expiration_date,
                    direction=option.direction.name,
                    style=option.style.name,
                    basic_asset=option.basic_asset,
                    updated_at=datetime.now()
                ))
            session.commit()

    def query_data(self, filters):
        with self.Session() as session:
            return session.query(Option).filter_by(**filters).all()


options_database = OptionsDatabase()
