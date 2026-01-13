# api_client.py
from datetime import datetime

import requests
from tinkoff.invest import AsyncClient, RequestError, InstrumentType, GetAssetFundamentalsRequest, MoneyValue
from bs4 import BeautifulSoup

from token import TOKEN


class TinkoffAPIClient:
    # Глобальная переменная класса для единого асинхронного подключения

    def __init__(self):
        """
        Инициализирует TinkoffAPIClient, создавая единое асинхронное подключение к API, если оно ещё не создано.
        """
        self.token = TOKEN

    async def get_shares(self):
        """
        Асинхронно запрашивает список всех акций из Tinkoff API.
        :return: Список объектов акций.
        :raises Exception: Если запрос не удался.
        """
        try:
            async with AsyncClient(self.token) as client:
                response = await client.instruments.shares()
                return response.instruments
        except RequestError as e:
            raise Exception(f"Ошибка при запросе акций: {str(e)}")

    async def get_bonds(self):
        """
        Асинхронно запрашивает список всех облигаций из Tinkoff API.
        :return: Список объектов облигаций.
        :raises Exception: Если запрос не удался.
        """
        try:
            async with AsyncClient(self.token) as client:
                response = await client.instruments.bonds()
                return response.instruments
        except RequestError as e:
            raise Exception(f"Ошибка при запросе облигаций: {str(e)}")

    async def get_etfs(self):
        """
        Асинхронно запрашивает список всех ETF из Tinkoff API.
        :return: Список объектов ETF.
        :raises Exception: Если запрос не удался.
        """
        try:
            async with AsyncClient(self.token) as client:
                response = await client.instruments.etfs()
                return response.instruments
        except RequestError as e:
            raise Exception(f"Ошибка при запросе ETF: {str(e)}")

    async def get_futures(self):
        """
        Асинхронно запрашивает список всех фьючерсов из Tinkoff API.
        :return: Список объектов фьючерсов.
        :raises Exception: Если запрос не удался.
        """
        try:
            async with AsyncClient(self.token) as client:
                response = await client.instruments.futures()
                return response.instruments
        except RequestError as e:
            raise Exception(f"Ошибка при запросе фьючерсов: {str(e)}")

    async def get_options(self):
        """
        Асинхронно запрашивает список всех опционов из Tinkoff API.
        :return: Список объектов опционов.
        :raises Exception: Если запрос не удался.
        """
        try:
            async with AsyncClient(self.token) as client:
                response = await client.instruments.options()
                return response.instruments
        except RequestError as e:
            raise Exception(f"Ошибка при запросе опционов: {str(e)}")

    async def get_currencies(self):
        """
        Асинхронно запрашивает список всех валют из Tinkoff API.
        :return: Список объектов валют.
        :raises Exception: Если запрос не удался.
        """
        try:
            async with AsyncClient(self.token) as client:
                response = await client.instruments.currencies()
                if not [instr for instr in response.instruments if "eur" in instr.ticker.lower()]:
                    eur = await self.get_instrument_by_figi(figi="BBG0013HJJ31")
                    eur.iso_currency_name = "eur"
                    eur.nominal = MoneyValue(units=1, nano=0, currency="eur")
                    response.instruments.append(eur)
                return response.instruments
        except RequestError as e:
            raise Exception(f"Ошибка при запросе валют: {str(e)}")

    async def get_commodity(self):
        """
        Асинхронно запрашивает список всех валют из Tinkoff API.
        :return: Список объектов InstrumentsShort только по индексам и товарам.
        """
        result = set()
        keywords = [
            "DAX", "STOXX", "RGBI", "SSE", "FTSE", "HSI", "RTSI", "IMOEX", "IMOEX2", "RVI",  # Индексы
            "LCOc1", "NG", "XAU", "XAG", "XPT", "XPD",  # Индексы на товары
        ]
        try:
            async with AsyncClient(self.token) as client:
                for keyword in keywords:
                    instruments = await client.instruments.find_instrument(query=keyword)
                    for instrument in instruments.instruments:
                        if instrument.lot == 0:
                            result.add(instrument)
            return list(result)
        except RequestError as e:
            raise Exception(f"Ошибка при запросе индексов и товаров: {str(e)}")

    async def get_instrument_by_figi(self, figi):
        """
        Асинхронно запрашивает информацию об одном активе по FIGI.
        :param figi: FIGI актива.
        :return: Объект инструмента из Tinkoff API.
        :raises Exception: Если запрос не удался.
        """
        try:
            async with AsyncClient(self.token) as client:
                response = await client.instruments.get_instrument_by(id_type=1, id=figi)
                return response.instrument
        except RequestError as e:
            raise Exception(f"Ошибка при запросе актива по FIGI {figi}: {str(e)}")

    async def get_candles(self, figi, from_, to, interval):
        """
        Асинхронно запрашивает свечи по активу (FIGI) от from_ до to.
        :param figi: FIGI актива.
        :param from_: Время начала (datetime).
        :param to: Время конца (datetime).
        :param interval: Интервал свеч (например, 'day', 'hour').
        :return: Список объектов свеч.
        :raises Exception: Если запрос не удался.
        """
        try:
            async with AsyncClient(self.token) as client:
                response = await client.market_data.get_candles(
                    figi=figi,
                    from_=from_,
                    to=to,
                    interval=interval
                )
                return response.candles
        except RequestError as e:
            raise Exception(f"Ошибка при запросе свечей: {str(e)}")

    async def get_market_prices(self, figi):
        """
        Асинхронно запрашивает текущую рыночную цену актива по FIGI.
        :param figi: FIGI актива.
        :return: Объект с последней ценой или None, если цена недоступна.
        :raises Exception: Если запрос не удался.
        """
        try:
            async with AsyncClient(self.token) as client:
                response = await client.market_data.get_last_prices(figi=[figi])
                return response.last_prices[0] if response.last_prices else None
        except RequestError as e:
            raise Exception(f"Ошибка при запросе рыночной цены: {str(e)}")

    async def get_bond_coupons(self, figi: str, from_: datetime = None, to: datetime = None) -> list:
        """
        Асинхронно запрашивает купоны для облигации по FIGI из Tinkoff API.
        :param figi: FIGI облигации.
        :param from_: Начальная дата (datetime, опционально).
        :param to: Конечная дата (datetime, опционально).
        :return: Список словарей с данными купонов в стандартизированном формате.
        :raises Exception: Если запрос не удался.
        """
        try:
            async with AsyncClient(self.token) as client:
                # Если даты не указаны, запрашиваем с начала истории до текущего времени
                if from_ is None:
                    from_ = datetime(1970, 1, 1)  # Начало эпохи Unix
                if to is None:
                    to = datetime.utcnow()

                response = await client.instruments.get_bond_coupons(
                    figi=figi,
                    from_=from_,
                    to=to
                )
                # Преобразуем ответ в стандартизированный формат выплат
                return [
                    {
                        "coupon_date": coupon.coupon_date,
                        "pay_one_bond": coupon.pay_one_bond,
                        "payment_type": "coupon",
                        "fix_date": coupon.fix_date,
                        "coupon_start_date": coupon.coupon_start_date,
                        "coupon_end_date": coupon.coupon_end_date,
                        "coupon_period": coupon.coupon_period,
                        "coupon_type": coupon.coupon_type,
                        "coupon_number": coupon.coupon_number,
                    }
                    for coupon in sorted(response.events, key=lambda x: x.coupon_date)
                ]
        except RequestError as e:
            raise Exception(f"Ошибка при запросе купонов для {figi}: {str(e)}")
        # Coupon(figi='TCS00A107D74', coupon_date=datetime.datetime(2025, 10, 3, 0, 0, tzinfo=datetime.timezone.utc), coupon_number=22, fix_date=datetime.datetime(2025, 10, 2, 0, 0, tzinfo=datetime.timezone.utc), pay_one_bond=MoneyValue(currency='rub', units=7, nano=750000000), coupon_type=<CouponType.COUPON_TYPE_FIX: 5>, coupon_start_date=datetime.datetime(2025, 9, 3, 0, 0, tzinfo=datetime.timezone.utc), coupon_end_date=datetime.datetime(2025, 10, 3, 0, 0, tzinfo=datetime.timezone.utc), coupon_period=30)

    async def get_dividends(self, figi: str, from_: datetime = None, to: datetime = None) -> list:
        """
        Асинхронно запрашивает дивиденды для акции или ETF по FIGI из Tinkoff API.
        :param figi: FIGI акции или ETF.
        :param from_: Начальная дата (datetime, опционально).
        :param to: Конечная дата (datetime, опционально).
        :return: Список словарей с данными дивидендов в стандартизированном формате.
        :raises Exception: Если запрос не удался.
        """
        try:
            async with AsyncClient(self.token) as client:
                # Если даты не указаны, запрашиваем с начала истории до текущего времени
                if from_ is None:
                    from_ = datetime(2000, 1, 1)  # Начало эпохи Unix
                if to is None:
                    to = datetime.utcnow()

                response = await client.instruments.get_dividends(
                    figi=figi,
                    from_=from_,
                    to=to
                )
                # Преобразуем ответ в стандартизированный формат выплат
                return [
                    {
                        "close_price": dividend.close_price,
                        "created_at": dividend.created_at,
                        "declared_date": dividend.declared_date,
                        "dividend_net": dividend.dividend_net,
                        "last_buy_date": dividend.last_buy_date,
                        "payment_date": dividend.payment_date,
                        "record_date": dividend.record_date,
                        "yield_value": dividend.yield_value,
                        "regularity": dividend.regularity,
                        "dividend_type": dividend.dividend_type,
                    }
                    for dividend in response.dividends
                ]
        except RequestError as e:
            raise Exception(f"Ошибка при запросе дивидендов для {figi}: {str(e)}")
        # Dividend(dividend_net=MoneyValue(currency='rub', units=907, nano=0), payment_date=datetime.datetime(2024, 12, 31, 0, 0, tzinfo=datetime.timezone.utc), declared_date=datetime.datetime(2024, 12, 15, 0, 0, tzinfo=datetime.timezone.utc), last_buy_date=datetime.datetime(2024, 12, 16, 0, 0, tzinfo=datetime.timezone.utc), dividend_type='', record_date=datetime.datetime(2024, 12, 17, 0, 0, tzinfo=datetime.timezone.utc), regularity='', close_price=MoneyValue(currency='rub', units=3982, nano=0), yield_value=Quotation(units=22, nano=780000000), created_at=datetime.datetime(2024, 12, 17, 23, 47, 10, 707835, tzinfo=datetime.timezone.utc))


class SmartLabScraper:
    """Класс для парсинга фундаментальных данных с Smart-Lab.ru."""

    # Константы
    BASE_URL = "https://smart-lab.ru/q/{ticker}/f/{period}/"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/91.0.4472.124'
    }
    METRICS_MAP = [
        'date',             # Дата отчета
        'net_income',       # Чистая прибыль (млрд руб)
        'bank_assets',      # Активы банка (млрд руб, для банков)
        'assets',           # Активы (млрд руб, для не-банков)
        'bank_margin',      # Рентабельность банка (%)
        'net_margin',       # Чистая рентабельность (%)
        'market_cap',       # Рыночная капитализация (млрд руб)
        'ev',               # Стоимость компании - долги (млрд руб)
        'eps',              # Прибыль на акцию (руб)
        'p_e',              # Мультипликатор P/E (цена/прибыль, без ед.)
        'p_b',              # Мультипликатор P/B (цена/баланс, без ед.)
        'roe',              # Рентабельность капитала (%)
        'roa'               # Рентабельность активов (%)
    ]

    def __init__(self):
        """Инициализация единственного объекта для парсинга."""
        self.session = requests.Session()  # Переиспользуем сессию
        self.session.headers.update(self.HEADERS)

    def _make_request(self, ticker: str, period: str) -> str | None:
        """Делает HTTP-запрос к Smart-Lab."""
        if period not in ['y', 'q']:
            print(f"Неверный period для {ticker}: должен быть 'y' или 'q'")
            return None

        url = self.BASE_URL.format(ticker=ticker, period=period)
        resp = self.session.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        html = resp.text
        del resp
        return html

    def _parse_table(self, html: str, ticker: str, period: str) -> list:
        """Парсит таблицу из HTML, возвращает список словарей."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table', class_='simple-little-table financials')
            if not table:
                print(f"Таблица не найдена для {ticker}")
                del soup
                return []

            # Шаг 2: Ищем header_row и создаём список словарей
            header_row = table.find('tr', class_='header_row')
            periods = ['unknown']
            if header_row:
                headers = [td.text.strip() for td in header_row.find_all('td')]
                periods = headers[1:-2] if len(headers) > 3 else ['unknown']  # Пропускаем первые два столбца и LTM

            # Создаём список словарей (без ключей метрик)
            data = [
                {
                    'ticker': ticker,
                    'period': period_val,
                } for period_val in periods
            ]

            # Шаг 3: Цикл по строкам tr, ищем селекторы из METRICS_MAP
            for row in table.find_all('tr'):
                field = row.get('field')
                if not field or field not in self.METRICS_MAP:
                    continue

                cells = row.find_all(['th', 'td'])
                if len(cells) < 2:
                    continue

                # Шаг 4: Извлекаем значения и добавляем в словари
                for i, cell in enumerate(cells[3:-1]):  # Пропускаем первые два столбца и LTM
                    if i >= len(periods):
                        break
                    value = cell.text.strip().replace(' ', '').replace(',', '.').replace('%', '')
                    if value.count(".") <= 1 and value.replace('.', '').replace('-', '').isdigit():
                        value = float(value)

                    # Добавляем ключ/значение в словарь для текущего периода
                    for d in data:
                        if d['period'] == periods[i]:
                            d[field] = value
                            break
            return data
        except Exception as e:
            print(f"Ошибка парсинга таблицы для {ticker}: {str(e)}")
            return []

    def _format_data(self, data: list, ticker: str, period: str) -> dict | list | None:
        """Форматирует данные в словарь или список словарей, заменяя bank_assets на assets."""
        if not data:
            return None

        result = []
        for item in data:
            # Создаём новый словарь, заменяя bank_assets на assets
            formatted_item = {
                'ticker': item['ticker'],
                'period': item['period'],
            }
            # Копируем все ключи, заменяя bank_assets на assets
            for key, value in item.items():
                if key == 'bank_assets':
                    formatted_item['assets'] = value
                elif 'margin' in key:
                    formatted_item['margin'] = value
                elif key not in ['ticker', 'period']:
                    formatted_item[key] = value

            if formatted_item["date"]:      # Если есть дата отчета, то добавляем
                result.append(formatted_item)
        return result

    def get(self, ticker: str, period: str = 'y') -> dict | list | None:
        """
        Центральный метод для получения фундаментальных данных.

        Args:
            ticker (str): Тикер акции (например, 'SBER').
            period (str): 'y' для годовых, 'q' для квартальных отчётов.

        Returns:
            dict | list: Словарь (последний период) или список словарей (история).
                         Ключи: ticker, period_year/period_quarter, net_income, bank_assets/assets, etc.
                         None при ошибке.
        """
        html = self._make_request(ticker, period)
        if not html:
            return None

        raw_data = self._parse_table(html, ticker, period)
        if not raw_data:
            return None

        result = self._format_data(raw_data, ticker, period)
        del html, raw_data
        return result

    def __del__(self):
        """Закрывает сессию при удалении объекта."""
        self.session.close()


# Глобальные экземпляры
tinkoff_api_client = TinkoffAPIClient()
scraper = SmartLabScraper()
