"""
Проверка подготовки данных для графиков (без открытия окон matplotlib).
Сами функции draw.* возвращают fig, поэтому мы проверяем,
что DataFrame'ы для графиков строятся корректно.
"""

import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import calc  # noqa: E402


# Создаём тестовый портфель
def make_portfolio():
    return [
        calc.PortfolioRow("A", 50, 12, 5, 0),
        calc.PortfolioRow("B", 50, 8, 0, 1),
    ]


def make_expenses():
    return [
        calc.ExpenseRow("еда", "", "хлеб", 100, "мес", True),
        calc.ExpenseRow("еда", "", "молоко", 200, "мес", True),
        calc.ExpenseRow("транспорт", "", "метро", 50, "мес", True),
    ]


def test_expenses_for_pie_columns():
    """Подготовка данных для pie: name, amount, без мелочи."""
    rows = make_expenses()
    pie = calc.expenses_for_pie(rows)
    assert list(pie.columns) == ["name", "amount"]
    assert pie["amount"].sum() == 350


def test_time_vs_capital_prepares_dataframe():
    """Подготовка данных для линейного графика «срок vs капитал»."""
    df = calc.time_vs_capital(
        capital_values=[100, 1000, 10000, 100000],
        target_capital=200000,
        annual_return_percent=10,
    )
    assert list(df.columns) == ["capital", "years", "achievable"]
    assert len(df) == 4


def test_time_vs_return_prepares_dataframe():
    """Подготовка данных для графика «срок vs доходность»."""
    df = calc.time_vs_return(
        return_values_percent=[1, 5, 10, 15],
        current_capital=1000,
        target_capital=10000,
    )
    assert list(df.columns) == ["return_percent", "years", "achievable"]
    assert len(df) == 4
    # 0% должен быть недостижим
    df0 = calc.time_vs_return([0], current_capital=1000, target_capital=10000)
    assert bool(df0.iloc[0]["achievable"]) is False


def test_time_vs_expenses_prepares_dataframe():
    """Подготовка данных для графика «срок vs расходы»."""
    df = calc.time_vs_expenses(
        expense_values=[0, 100, 1000, 100000],
        current_capital=100000,
        target_capital=500000,
        annual_return_percent=5,
    )
    assert list(df.columns) == ["monthly_expenses", "years", "achievable"]
    assert len(df) == 4


def test_portfolio_expected_return_for_draw():
    """Данные портфеля, которые идут в heatmap: доходность портфеля."""
    p = make_portfolio()
    expected = calc.portfolio_expected_return_percent(p)
    # 0.5 * 12 + 0.5 * 8 = 10
    assert abs(expected - 10.0) < 1e-9
