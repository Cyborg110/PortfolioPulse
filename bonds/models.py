# /bonds/models.py
import asyncio
from typing import List, Dict
from datetime import datetime, timedelta

from t_tech.invest import CandleInterval

from settings import Settings
from base.models import BaseAsset
from bonds.database import bonds_database
from payments.coupons import Coupons
from candles.models import MultiTimeframeCandles
from currencies.converter import converter


# TODO: Добавить валюту на номинал (сильно влияет на расчеты)
class Bond(BaseAsset):
    interval = CandleInterval.CANDLE_INTERVAL_DAY

    def __init__(self, identifier, identifier_type='ticker'):
        super().__init__(identifier, identifier_type)
        # Дополнительные переменные
        self.sector = None                      # Сектор
        self.nominal = None                     # Номинал
        self.nominal_currency = None            # Валюта номинала
        self.initial_nominal = None             # Начальный номинал (в случае амортизации)
        self.initial_nominal_currency = None    # Валюта начального номинала
        self.coupon_quantity_per_year = None    # Кол-во купонов в год
        self.aci_value = None                   # НКД
        self.aci_value_currency = None          # Валюта НКД
        self.issue_size = None                  # Выпущенные облигации
        self.issue_size_plan = None             # План по выпуску облигаций
        self.maturity_date = None               # Дата погашения
        self.placement_date = None              # Дата размещения
        self.floating_coupon_flag = None        # Флаг плавающего купона
        self.amortization_flag = None           # Флаг амортизации
        self.risk_level = None                  # Уровень риска
        self.is_yield_approximate = False       # Флаг приблизительного расчёта

        # Дополнительные переменные для метрик
        self.candles: [MultiTimeframeCandles, None] = None
        self.payments: [Coupons, None] = None
        self.days_to_maturity: [datetime, None] = None  # Дней до погашения
        self.current_yield: [float, None] = None        # Купонная доходность
        self.total_return: [float, None] = None         # Доходность без реинвеста (все_выплаты / текущая_цена)
        self.ytm: [float, None] = None                  # Доходность к оферте/погашению
        self.macaulay_duration: [float, None] = None    # Дюрация (среднее кол-во лет для возврата денег) блокировка по выбранной ставки на кол-во лет
        self.price_drop_on_1pct: [float, None] = None   # На сколько упадет цена при росте ставки на 1%

        self._get_params()

    def _get_params(self) -> None:
        """
        Заполняет переменные класса данными из базы данных через BondsDatabase.
        """
        record = bonds_database.get_instrument_by_identifier(self.identifier, self.identifier_type)
        if record:
            self._update_from_record(record)
        else:
            raise ValueError(f"Облигация с {self.identifier_type} {self.identifier} не найдена в базе")

        self.candles = MultiTimeframeCandles(figi=self.figi, factor=self.nominal/100)
        self.payments = Coupons(figi=self.figi, candles=self.candles[CandleInterval.CANDLE_INTERVAL_DAY])

    def _update_from_record(self, record):
        """
        Обновляет атрибуты класса из записи базы данных.
        """
        self.figi = record.figi
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
        self.nominal = record.nominal
        self.nominal_currency = record.nominal_currency         # /////
        self.initial_nominal = record.initial_nominal
        self.initial_nominal_currency = record.initial_nominal_currency     # /////
        self.coupon_quantity_per_year = record.coupon_quantity_per_year
        self.aci_value = record.aci_value
        self.aci_value_currency = record.aci_value_currency                 # //////
        self.issue_size = record.issue_size
        self.issue_size_plan = record.issue_size_plan
        self.maturity_date = record.maturity_date
        self.placement_date = record.placement_date
        self.floating_coupon_flag = record.floating_coupon_flag
        self.amortization_flag = record.amortization_flag
        self.risk_level = record.risk_level
        self.updated_at = record.updated_at

    def calculate_days_to_maturity(self):
        """
        Кол-во дней до погашения.
        :return:
        """
        self.days_to_maturity = (self.maturity_date - datetime.utcnow()).days

    def calculate_current_yield(self) -> float:
        """
        Рассчитывает купонную доходность (Current Yield).
        :return: Купонная доходность в процентах (годовая).
        """
        # Получаем последнюю рыночную цену
        candle = self.candles[self.interval].last_candle
        if not candle or candle.close <= 0:
            self.current_yield = 0.0
            return self.current_yield

        self.current_yield = (self.payments.amount_year / candle.close) * 100 if self.payments.amount_year else 0.0

        return round(self.current_yield, 2)

    def calculate_total_return(self) -> float:
        """
        Рассчитывает доходность к погашению как отношение суммы всех выплат к текущей цене.
        Не учитывает реинвестиции.
        :return: total_return в процентах (годовая).
        """
        # Получаем cash flows из Coupons
        cash_flows = self.payments.get_future_cash_flows(
            nominal=self.nominal,
            amortization_flag=self.amortization_flag,
            maturity_date=self.maturity_date,
            floating_coupon_flag=self.floating_coupon_flag
        )

        candle = self.candles[self.interval].last_candle
        if not cash_flows or not candle or candle.close <= 0:
            self.total_return = 0.0
            return self.total_return

        price = candle.close + self.aci_value
        cash_flow_values = [cf["amount"] for cf in cash_flows]

        self.total_return = sum(cash_flow_values) * 100 / price - 100 or 0.0

        count_years = self.days_to_maturity / 365
        self.total_return /= count_years if count_years > 0 else 1 / 365
        return self.total_return

    def calculate_ytm(self) -> float:
        """
        Yield to Maturity (YTM) — внутренняя норма доходности с реинвестированием.
        """
        cash_flows = self.payments.get_future_cash_flows(
            nominal=self.nominal,
            amortization_flag=self.amortization_flag,
            maturity_date=self.maturity_date,
            floating_coupon_flag=self.floating_coupon_flag
        )

        candle = self.candles[self.interval].last_candle
        if not cash_flows or not candle or candle.close <= 0:
            self.ytm = 0.0
            return 0.0

        dirty_price = candle.close + self.aci_value
        if dirty_price <= 0:
            self.ytm = 0.0
            return 0.0

        now = datetime.utcnow()

        def npv(y: float) -> float:
            total = 0.0
            for cf in cash_flows:
                days = (cf["date"] - now).days
                if days < 0:
                    continue
                years = days / 365.25
                total += cf["amount"] / (1 + y) ** years
            return total - dirty_price

        low, high = -0.99, 2.0
        while high - low > 1e-10:
            mid = (low + high) / 2
            if npv(mid) > 0:
                low = mid
            else:
                high = mid

        self.ytm = round(low * 100, 4) or 0.0
        self.is_yield_approximate = self.payments.is_approximate or self.floating_coupon_flag
        return self.ytm

    def calculate_macaulay_duration(self) -> float:
        """
        Macaulay Duration в годах: средневзвешенное время возврата капитала.
        """
        cash_flows = self.payments.get_future_cash_flows(
            nominal=self.nominal,
            amortization_flag=self.amortization_flag,
            maturity_date=self.maturity_date,
            floating_coupon_flag=self.floating_coupon_flag
        )
        candle = self.candles[self.interval].last_candle
        ytm = self.ytm / 100  # в долях
        if not cash_flows or not candle or ytm <= -1:
            self.macaulay_duration = 0.0
            return 0.0

        now = datetime.utcnow()
        weighted_sum = 0.0
        pv_sum = 0.0

        for cf in cash_flows:
            days = (cf["date"] - now).days
            if days < 0:
                continue
            t = days / 365.25  # время в годах
            pv = cf["amount"] / (1 + ytm) ** t
            weighted_sum += t * pv
            pv_sum += pv

        if pv_sum <= 0:
            return 0.0

        mac_duration = weighted_sum / pv_sum
        self.macaulay_duration = round(mac_duration, 3)
        return self.macaulay_duration

    def calculate_price_drop_on_1pct_rate_rise(self) -> float:
        """
        На сколько % упадёт цена, если ставка вырастет на 1%.
        Использует Modified Duration.
        """
        ytm = self.ytm / 100
        if ytm <= -1 or not self.macaulay_duration:
            self.price_drop_on_1pct = 0.0
            return 0.0

        mod_duration = self.macaulay_duration / (1 + ytm)
        price_drop_pct = mod_duration * 1.0  # 1% = 0.01 * 100
        self.price_drop_on_1pct = round(price_drop_pct, 3)
        return self.price_drop_on_1pct

    def calculate_metrics(self) -> None:
        """
        Расчёт всех метрик для облигации с учётом амортизации и плавающего купона.
        """
        # Загрузка данных
        self.candles[self.interval].load_candles()
        self.payments.load_payments()

        # =================== Конвертация =================== #
        # НКД
        if self.aci_value_currency != Settings.Converter.BASE_CURRENCY:
            self.aci_value = converter[self.aci_value_currency].value_to(self.aci_value, self.updated_at)
            self.aci_value_currency = Settings.Converter.BASE_CURRENCY
        # Номиналы
        if self.nominal_currency != Settings.Converter.BASE_CURRENCY:
            self.nominal = converter[self.nominal_currency].value_to(self.nominal, self.updated_at)
            self.initial_nominal = converter[self.initial_nominal_currency].value_to(self.initial_nominal, self.updated_at)

            converter[self.nominal_currency].candles_to(self.candles[CandleInterval.CANDLE_INTERVAL_DAY])
            self.nominal_currency = Settings.Converter.BASE_CURRENCY
            self.initial_nominal_currency = Settings.Converter.BASE_CURRENCY
        # Выплаты
        if self.payments.payments and (payments_currency := self.payments.payments[0].currency) != Settings.Converter.BASE_CURRENCY:
            converter[payments_currency].payments_to(self.payments)

        # =================== Расчёт статических метрик свечей ===================
        if self.candles and self.candles[self.interval]:
            self.candles.calculate_static(use_buffer=True)

        self.payments.calculate_coupon_yeild()      # Расчет доходности каждого купона
        self.payments.calculate_amount_year(floating_coupon_flag=self.floating_coupon_flag,
                                            coupon_quantity_per_year=self.coupon_quantity_per_year)       # Прогноз будущего годового купона

        self.calculate_days_to_maturity()
        self.calculate_current_yield()
        self.calculate_total_return()
        self.calculate_ytm()
        self.calculate_macaulay_duration()
        self.calculate_price_drop_on_1pct_rate_rise()

        # =================== Очистка буферов ===================
        if self.payments:
            self.payments.clear_buffer()
        if self.candles and self.candles[self.interval]:
            self.candles[self.interval].clear_buffer()

    async def update_candles(self) -> None:
        """
        Обновление свечек в БД (по self.interval).
        """
        if self.candles and self.candles[self.interval] and self.first_1day_candle_date and self.nominal:
            await self.candles[self.interval].update_candles(from_time=self.first_1day_candle_date)

    async def update_payments(self) -> None:
        """
        Обновление выплат в БД.
        :return: None
        """
        await self.payments.update_payments(to_time=self.maturity_date + timedelta(days=1))

    def drop(self):
        """
        Очистка БД для актива.
        :return:
        """
        self.candles.drop()
        self.payments.drop()

    def __str__(self) -> str:
        current_price = self.candles[CandleInterval.CANDLE_INTERVAL_DAY].price if self.candles[
            CandleInterval.CANDLE_INTERVAL_DAY].price else 0
        return (
            f"Тикер: {self.ticker}\n"
            f"FIGI: {self.figi}\n"
            f"Название: {self.name}\n"
            f"Валюта: {self.currency.upper()}\n"
            f"Цена: {current_price:.2f}; НКД: {self.aci_value:.2f}\n"
            f"Номинал: {self.nominal:.2f}\n"
            f"Купонов в год: {self.coupon_quantity_per_year}\n"
            f"Годовая купонная доходность: {self.payments.amount_year:.2f} ({self.current_yield:.2f}%)\n"
            f"Полная доходность: {self.total_return:.2f} %\n"
            f"YTM: {self.ytm:.2f}% {'(приближённо)' if self.is_yield_approximate else ''}\n"
            f"Дюрация: {self.macaulay_duration:.3f}; Падение цены на 1%: {self.price_drop_on_1pct:.3f}%\n"
            f"Дней до погашения: {self.maturity_date.strftime('%Y-%m-%d') if self.maturity_date else 'N/A'} ({self.days_to_maturity} дней\n"
            f"Размер выпуска: {self.issue_size:,} (план: {self.issue_size_plan:,})\n"
            f"Сектор: {self.sector or 'N/A'};\tСтрана риска: {self.country_of_risk or 'N/A'}\n"
            f"Риск: {self.risk_level}\n"
            f"Амортизация: {self.amortization_flag}; Плавающий купон: {self.floating_coupon_flag}\n"
            f"{self.candles[CandleInterval.CANDLE_INTERVAL_DAY]}"
        )


class Bonds:
    """
    Класс для массовой работы с облигациями, соответствующими фильтрам.
    """

    def __init__(self, filters: Dict = None):
        """
        Инициализация объекта с облигациями, отфильтрованными по заданным критериям.
        :param filters: Словарь фильтров (например, {"currency": "RUB", "for_qual_investor_flag": False}).
        """
        self.filters = filters or {}
        self.bonds: List[Bond] = []
        self._load_bonds()

    def _load_bonds(self):
        """
        Загружает облигации из базы данных по заданным фильтрам и создаёт список объектов Bond.
        """
        try:
            # Запрашиваем записи из базы данных
            bond_records = bonds_database.query_data(self.filters)
            # Создаём объекты Bond для каждого FIGI
            self.bonds = [Bond(record.figi, identifier_type='figi') for record in bond_records]
        except Exception as e:
            print(f"Ошибка при загрузке облигаций: {str(e)}")
            self.bonds = []

    async def update_candles(self, sleep: float = 0):
        """
        Обновляет свечи для всех облигаций в списке.
        :param sleep: Время засыпания между запросами.
        """
        count = len(self.bonds)
        i = 0
        for bond in self.bonds:
            i += 1
            try:
                await bond.update_candles()
                await asyncio.sleep(sleep)
                print(f"{i}/{count} {bond.ticker} свечи обновлены!")
            except Exception as e:
                print(f"Не удалось обновить для {bond.ticker}: {e}")

    async def update_payments(self, sleep: float = 0):
        """
        Обновляет свечи для всех акций в списке.
        :param sleep: Время засыпания между запросами.
        """
        count = len(self.bonds)
        i = 0
        for bond in self.bonds:
            i += 1
            try:
                await bond.update_payments()
                await asyncio.sleep(sleep)
                print(f"{i}/{count} {bond.ticker} купоны обновлены!")
            except Exception as e:
                print(f"Не удалось обновить купоны для {bond.ticker}: {e}")

    def calculate_metrics(self):
        """
        Расчет метрик для всех облигаций.
        :return:
        """
        for bond in self.bonds:
            bond.calculate_metrics()

    def __iter__(self):
        """
        Позволяет итерироваться по списку облигаций.
        """
        return iter(self.bonds)
