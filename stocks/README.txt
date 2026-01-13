Модуль stocks — полный аналог модулей bonds и etfs, но для обыкновенных и привилегированных акций.
Содержит всё необходимое для массового анализа, обновления данных и расчёта метрик.

Структура модуля
├── __init__.py        → re-export Stock, Stocks
├── models.py          → основные классы Stock и Stocks
├── database.py        → таблица stocks (список всех акций с метаданными)
└── README.txt         ← ты читаешь его сейчас

================================================================================
Главные классы
================================================================================

1. Stock → наследует BaseAsset
   Полноценный объект одной акции. Поля (важные для анализа):

   • Основные:
     ticker, figi, name, currency, lot, sector, country_of_risk

   • Торговые флаги:
     for_iis_flag, for_qual_investor_flag, buy_available_flag и т.д.

   • Объекты-подмодули:
     self.candles  → MultiTimeframeCandles (дневки + часовки)
     self.payments → Dividends (дивиденды)

   После вызова calculate_metrics() появляются все метрики свечей + все дивидендные метрики.

2. Stocks → контейнер для массовой работы
   Аналог Bonds / Etfs:
   • Загружает все акции по фильтрам
   • update_candles(), update_payments(), calculate_metrics() — массовые
   • __iter__() — можно for stock in stocks:

================================================================================
Полный список метрик, которые считаются для акции
================================================================================

1. Из модуля candles (дневной таймфрейм)
   • volatility
   • avg_volume
   • avg_price_volume
   • average_return
   • sharpe_ratio
   • max_drawdown
   • atr_14

2. Из модуля payments/dividends (объект self.payments)
   • payout_frequency         → сколько раз в год в среднем платят
   • dividend_cagr_3y         → рост дивидендов за 3 года, %
   • dividend_stability       → стабильность выплат (0..1)
   • trailing_yield           → дивидендная доходность за последние 12 мес, %
   • forward_yield            → ожидаемая годовая дивидендная доходность, % (главная!)
   • yield_plus_growth        → forward_yield + cagr_3y
   • risk_adj_yield           → forward_yield / volatility

   → Именно эти метрики используются в best_stocks() и best_etfs()

================================================================================
Как пользоваться
================================================================================

Одиночная акция:
    stock = Stock("SBER")                    # по тикеру
    # или
    stock = Stock("BBG004730N88", 'figi')

    await stock.candles.update_candles()     # если нужно свежие свечи
    await stock.payments.update_payments()   # дивиденды (раз в сутки достаточно)
    stock.calculate_metrics()                # всё сразу

    print(f"Forward yield: {stock.payments.forward_yield:.2f}%")
    print(f"Volatility: {stock.candles.volatility:.2%}")

Массовый анализ (пример best_stocks):
    stocks = Stocks(filters={"currency": "rub", "for_iis_flag": True})
    await stocks.update_candles(sleep=0.05)
    await stocks.update_payments(sleep=0.05)
    stocks.calculate_metrics()

    for stock in sorted(stocks.stocks,
                        key=lambda s: s.payments.forward_yield or 0,
                        reverse=True)[:20]:
        print(stock)

================================================================================
Важные детали
================================================================================

1. calculate_metrics() — один вызов делает всё:
   • candles.calculate_static()
   • payments.calculate_metrics()

2. Буферы (candles.candles и payments.payments) автоматически очищаются
   после calculate_metrics() — экономия памяти.

3. Если у акции нет дивидендов — все дивидендные метрики будут 0.0
   (forward_yield = 0, cagr = 0 и т.д.)

4. Конвертация валют:
   Если акция в USD/EUR/CNY и т.д. — в Stock.calculate_metrics() автоматически вызывается
   converter.convert() → все цены и дивиденды приводятся к RUB.
   Если валюта не поддерживается — остаётся как есть (без падения).

5. update_payments() — дергает API Тинькофф, ищет дивиденды.
   Делать раз в сутки или реже.

================================================================================
Пример реального использования в проекте
================================================================================

best_stocks.py → функция best_stocks():
    stocks = Stocks(filters=filters)
    if update:
        await stocks.update_candles(0.05)
        await stocks.update_payments(0.05)
    stocks.calculate_metrics()

    for stock in sorted(stocks.stocks,
                        key=lambda x: [x.candles.max_drawdown], reverse=True):
        ...

Именно поэтому модуль stocks полностью готов к использованию в скринерах,
сортировках, фильтрах и любых кастомных стратегиях.

================================================================================
Итог
================================================================================

Модуль stocks — полностью симметричен модулям bonds и etfs.
Работаете с акциями точно так же, как с облигациями и ETF:
    stock.candles  → все ценовые метрики
    stock.payments → все дивидендные метрики
    stock.calculate_metrics() → один вызов и всё готово

Никаких сюрпризов, никаких ручных вызовов — просто берёте и используете.