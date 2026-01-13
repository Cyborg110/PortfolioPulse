Модуль payments — единая точка работы со всеми выплатами (купоны облигаций и дивиденды акций/ETF).
Несмотря на то, что внутри лежат два разных типа выплат, это ОДИН модуль с общей архитектурой.

Структура модуля
├── __init__.py        → re-export нужных классов
├── models.py          → базовые PaymentBase / PaymentsBase
├── database.py        → общая таблица payments (FIGI + instrument_type + все поля)
├── coupons.py         → реализация купонов облигаций
└── dividends.py       → реализация дивидендов акций и ETF

Общая идея
Все выплаты хранятся в одной таблице payments, но имеют поле instrument_type:
- "bond"  → купоны
- "stock" → дивиденды акций
- "etf"   → дивиденды ETF

Главные классы

1. PaymentBase           → минимальный общий предок (payment_date + amount)
2. PaymentsBase          → общая логика загрузки/обновления/очистки буфера
3. Coupon → PaymentBase  → один купон
4. Coupons → PaymentsBase → набор купонов облигации
5. Dividend → PaymentBase → один дивиденд
6. Dividends → PaymentsBase → набор дивидендов акции/ETF

================================================================================
ВСЕ МЕТРИКИ, КОТОРЫЕ РАССЧИТЫВАЕТ МОДУЛЬ PAYMENTS
================================================================================

Для облигаций (класс Coupons)

После вызова bond.payments.calculate_metrics() (или отдельных методов) доступны:

1. На уровне каждого отдельного купона (Coupon)
   • yield_value          → доходность конкретного купона в % на дату выплаты
                            (amount / close_price_на_дату_выплаты * 100)

2. На уровне объекта Coupons
   • amount_year          → ожидаемый годовой купон в валюте номинала
                            (самая главная метрика для облигаций)
   • average_amount       → средний размер одного купона (исторический)
   • is_approximate       → True, если расчёт приблизительный
                            (плавающий купон + амортизация одновременно)

   Вспомогательные (используются внутри YTM):
   • calculate_amount_year(floating_coupon_flag, coupon_quantity_per_year)
   • get_future_cash_flows(nominal, amortization_flag, maturity_date, floating_coupon_flag)
        → список будущих денежных потоков для расчёта YTM/дюрации

Для акций и ETF (класс Dividends)

После вызова stock.payments.calculate_metrics() (или etf.payments.calculate_metrics()) доступны:

1. Частота и стабильность выплат
   • payout_frequency          → сколько раз в среднем в год платят дивиденды
                                  (365.25 / средний_интервал_между_выплатами)
   • dividend_stability        → 1 – коэффициент вариации годовых сумм
                                  (0 = нестабильно, 1 = идеально стабильно)

2. Рост дивидендов
   • dividend_cagr_3y          → CAGR дивидендов за последние 3 полных года, %

3. Текущие доходности
   • trailing_yield            → сумма дивидендов за последние 12 мес / текущая цена, %
   • forward_yield             → ожидаемая годовая дивидендная доходность, %
                                  (обычно = last_annual × frequency или следующая_объявленная × frequency)

4. Сводные и риск-аджастированные метрики
   • yield_plus_growth         → forward_yield + dividend_cagr_3y
   • risk_adj_yield            → forward_yield / волатильность (из candles.volatility)

   Внутренние (не публичные, но используются):
   • last_annual_dividend      → сумма дивидендов за последний полный календарный год
   • next_payment              → следующая объявленная выплата (если есть)

================================================================================
Краткая шпаргалка «что где брать»

Облигация:
    bond.payments.amount_year                → годовой купон (главное для сортировки)
    bond.payments.is_approximate             → понимать, насколько точен YTM
    [coupon.yield_value for coupon in bond.payments.payments] → доходность каждого купона

Акция / ETF:
    stock.payments.forward_yield             → ожидаемая дивидендная доходность (главное)
    stock.payments.dividend_cagr_3y
    stock.payments.dividend_stability
    stock.payments.trailing_yield
    stock.payments.yield_plus_growth
    stock.payments.risk_adj_yield

================================================================================
Как пользоваться (общий сценарий)

# Облигация
await bond.payments.update_payments()           # раз в сутки
bond.payments.calculate_metrics()               # считает amount_year и yield_value
print(f"Годовой купон: {bond.payments.amount_year:.2f}")

# Акция / ETF
await stock.payments.update_payments()
stock.payments.calculate_metrics()              # все 7 дивидендных метрик сразу
print(f"Forward yield: {stock.payments.forward_yield:.2f}%")

================================================================================
Важные нюансы

1. Буфер self.payments автоматически очищается в Bond/Stock/Etf.calculate_metrics()
   после расчётов — в памяти остаются только посчитанные метрики.

2. update_payments() — асинхронная, делает запрос в Tinkoff API.
   Достаточно выполнять раз в сутки (или реже).

3. Для облигаций с плавающим купоном + амортизацией → is_approximate = True,
   YTM будет помечен как приблизительный.

Итого: хотя код разнесён по двум файлам (coupons.py и dividends.py),
это один логический модуль payments с чётким разделением метрик по типу инструмента.
Работаете всегда через атрибут .payments у любого актива — всё остальное делается само.