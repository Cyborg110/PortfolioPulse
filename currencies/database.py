# /currencies/database.py
from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer
from datetime import datetime
from base.database import BaseDatabase, Base
from api_client import tinkoff_api_client


class Currency(Base):
    __tablename__ = "currencies"
    figi = Column(String, primary_key=True)             # Уникальный идентификатор инструмента
    position_uid = Column(String)                       # Дополнительный идентификатор инструмента
    ticker = Column(String)                             # Тикер для поиска (например, CNYRUBTODTOM)
    name = Column(String)                               # Название валюты (например, Китайский юань)
    currency = Column(String)                           # Валюта торгов (например, RUB)
    lot = Column(Integer)                               # Размер лота для торгов (например, 100000)
    country_of_risk = Column(String)                    # Страна риска (может быть пустой)
    min_price_increment = Column(Float)                 # Минимальный шаг цены (например, 0.00001)
    for_iis_flag = Column(Boolean)                      # Доступность для ИИС
    for_qual_investor_flag = Column(Boolean)            # Требуется статус квалифицированного инвестора
    buy_available_flag = Column(Boolean)                # Доступность для покупки
    sell_available_flag = Column(Boolean)               # Доступность для продажи
    api_trade_available_flag = Column(Boolean)          # Доступность торгов через API
    trading_status = Column(String)                     # Статус торгов (например, NOT_AVAILABLE_FOR_TRADING)
    first_1min_candle_date = Column(DateTime)           # Дата первой минутной свечи для исторических данных
    first_1day_candle_date = Column(DateTime)           # Дата первой дневной свечи для исторических данных
    iso_currency_name = Column(String)                  # ISO-код валюты (например, CNY)
    nominal = Column(Float)                             # Номинал валюты (например, 1 CNY)
    updated_at = Column(DateTime)                       # Время последнего обновления записи


class CurrenciesDatabase(BaseDatabase):
    def get_instrument_by_identifier(self, identifier, identifier_type):
        """
        Возвращает данные об валюте по идентификатору.
        :param identifier: Значение идентификатора (FIGI или ticker).
        :param identifier_type: Тип идентификатора ('figi' или 'ticker').
        :return: Объект модели Currency или None, если не найден.
        :raises Exception: Если запрос не удался.
        """
        try:
            with self.Session() as session:
                if identifier_type == 'figi':
                    return session.query(Currency).filter_by(figi=identifier).first()
                elif identifier_type == 'ticker':
                    return session.query(Currency).filter_by(ticker=identifier).first()
                else:
                    raise ValueError(f"Неподдерживаемый тип идентификатора: {identifier_type}")
        except Exception as e:
            raise Exception(f"Ошибка при запросе данных валюты по {identifier_type} {identifier}: {str(e)}")

    async def fetch_data(self):
        currencies = await tinkoff_api_client.get_currencies()
        with self.Session() as session:
            for currency in currencies:
                if currency.exchange in ["swap_cets"]:
                    continue    # Пропускаем свопы

                session.merge(Currency(
                    figi=currency.figi,
                    position_uid=currency.position_uid,
                    ticker=currency.ticker,
                    name=currency.name,
                    currency=currency.currency,
                    lot=currency.lot,
                    country_of_risk=currency.country_of_risk,
                    min_price_increment=currency.min_price_increment.units + currency.min_price_increment.nano / 1e9,
                    for_iis_flag=currency.for_iis_flag,
                    for_qual_investor_flag=currency.for_qual_investor_flag,
                    buy_available_flag=currency.buy_available_flag,
                    sell_available_flag=currency.sell_available_flag,
                    api_trade_available_flag=currency.api_trade_available_flag,
                    trading_status=currency.trading_status.name,
                    first_1min_candle_date=currency.first_1min_candle_date,
                    first_1day_candle_date=currency.first_1day_candle_date,
                    iso_currency_name=currency.iso_currency_name,
                    nominal=currency.nominal.units + currency.nominal.nano / 1e9,
                    updated_at=datetime.now()
                ))
            session.commit()

    def query_data(self, filters):
        with self.Session() as session:
            return session.query(Currency).filter_by(**filters).all()


currencies_database = CurrenciesDatabase()
