# /bonds/database.py
from sqlalchemy import Column, String, Float, DateTime, Boolean, Integer
from datetime import datetime

from base.database import BaseDatabase, Base
from api_client import tinkoff_api_client


# /bonds/database.py
class Bond(Base):
    __tablename__ = "bonds"
    figi = Column(String, primary_key=True)                     # Уникальный идентификатор инструмента
    position_uid = Column(String)                               # Дополнительный идентификатор инструмента
    ticker = Column(String)                                     # Тикер для поиска (например, RU000A107D74)
    name = Column(String)                                       # Название облигации (например, ЭнергоТехСервис 001P-05)
    currency = Column(String)                                   # Валюта торгов (например, RUB)
    class_code = Column(String)                                 # class_code актива (нужен для единичного запроса)
    lot = Column(Integer)                                       # Размер лота для торгов
    sector = Column(String)                                     # Сектор экономики (например, industrials)
    country_of_risk = Column(String)                            # Страна риска (например, RU)
    min_price_increment = Column(Float)                         # Минимальный шаг цены (например, 0.01)
    for_iis_flag = Column(Boolean)                              # Доступность для ИИС
    for_qual_investor_flag = Column(Boolean)                    # Требуется статус квалифицированного инвестора
    buy_available_flag = Column(Boolean)                        # Доступность для покупки
    sell_available_flag = Column(Boolean)                       # Доступность для продажи
    api_trade_available_flag = Column(Boolean)                  # Доступность торгов через API
    trading_status = Column(String)                             # Статус торгов (например, NOT_AVAILABLE_FOR_TRADING)
    first_1min_candle_date = Column(DateTime)                   # Дата первой минутной свечи для исторических данных
    first_1day_candle_date = Column(DateTime)                   # Дата первой дневной свечи для исторических данных
    nominal = Column(Float)                                     # Номинальная стоимость облигации (например, 706 RUB)
    nominal_currency = Column(String)                           # Валюта номинала (например, RUB, USD, EUR)
    initial_nominal = Column(Float)                             # Исходная номинальная стоимость (например, 1000 RUB)
    initial_nominal_currency = Column(String)                   # Валюта начального номинала (например, RUB, USD, EUR)
    coupon_quantity_per_year = Column(Integer)                  # Количество купонных выплат в год
    aci_value = Column(Float)                                   # Накопленный купонный доход (например, 8.49 RUB)
    aci_value_currency = Column(String)                         # Валюта НКД (например, RUB, USD, EUR)
    issue_size = Column(Integer)
    issue_size_plan = Column(Integer)
    maturity_date = Column(DateTime)                            # Дата погашения облигации
    placement_date = Column(DateTime)                           # Дата размещения облигации
    floating_coupon_flag = Column(Boolean)                      # Флаг плавающего купона
    amortization_flag = Column(Boolean)                         # Флаг амортизации (постепенное погашение номинала)
    risk_level = Column(String)                                 # Уровень риска (например, RISK_LEVEL_MODERATE)
    updated_at = Column(DateTime)                               # Время последнего обновления записи


class BondsDatabase(BaseDatabase):
    def get_instrument_by_identifier(self, identifier, identifier_type):
        """
        Возвращает данные об облигации по идентификатору.
        :param identifier: Значение идентификатора (FIGI или ticker).
        :param identifier_type: Тип идентификатора ('figi' или 'ticker').
        :return: Объект модели Bond или None, если не найден.
        :raises Exception: Если запрос не удался.
        """
        try:
            with self.Session() as session:
                if identifier_type == 'figi':
                    return session.query(Bond).filter_by(figi=identifier).first()
                elif identifier_type == 'ticker':
                    return session.query(Bond).filter_by(ticker=identifier).first()
                else:
                    raise ValueError(f"Неподдерживаемый тип идентификатора: {identifier_type}")
        except Exception as e:
            raise Exception(f"Ошибка при запросе данных облигации по {identifier_type} {identifier}: {str(e)}")

    async def fetch_data(self):
        bonds = await tinkoff_api_client.get_bonds()
        with self.Session() as session:
            for bond in bonds:
                session.merge(Bond(
                    figi=bond.figi,
                    position_uid=bond.position_uid,
                    ticker=bond.ticker,
                    name=bond.name,
                    currency=bond.currency,
                    class_code=bond.class_code,
                    lot=bond.lot,
                    sector=bond.sector,
                    country_of_risk=bond.country_of_risk,
                    min_price_increment=bond.min_price_increment.units + bond.min_price_increment.nano / 1e9,
                    for_iis_flag=bond.for_iis_flag,
                    for_qual_investor_flag=bond.for_qual_investor_flag,
                    buy_available_flag=bond.buy_available_flag,
                    sell_available_flag=bond.sell_available_flag,
                    api_trade_available_flag=bond.api_trade_available_flag,
                    trading_status=bond.trading_status,
                    first_1min_candle_date=bond.first_1min_candle_date,
                    first_1day_candle_date=bond.first_1day_candle_date,
                    nominal=bond.nominal.units + bond.nominal.nano / 1e9,
                    nominal_currency=bond.nominal.currency,
                    initial_nominal=bond.initial_nominal.units + bond.initial_nominal.nano / 1e9,
                    initial_nominal_currency=bond.initial_nominal.currency,
                    coupon_quantity_per_year=bond.coupon_quantity_per_year,
                    aci_value=bond.aci_value.units + bond.aci_value.nano / 1e9,
                    aci_value_currency=bond.aci_value.currency,
                    issue_size=bond.issue_size,
                    issue_size_plan=bond.issue_size_plan,
                    maturity_date=bond.maturity_date,
                    placement_date=bond.placement_date,
                    floating_coupon_flag=bond.floating_coupon_flag,
                    amortization_flag=bond.amortization_flag,
                    risk_level=bond.risk_level if bond.risk_level else None,
                    updated_at=datetime.now()
                ))
            session.commit()

    def query_data(self, filters):
        with self.Session() as session:
            return session.query(Bond).filter_by(**filters).all()


bonds_database = BondsDatabase()
