"""
Тесты финансового ядра (calc.py).
Проверяются математические результаты и edge cases.
"""

import math
import os
import sys

import pytest

# Добавляем src/ в sys.path, чтобы тесты запускались и из pytest,
# и напрямую — без установки пакета.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import calc  # noqa: E402


# ---------------------------------------------------------------------------
# Проценты и временные преобразования
# ---------------------------------------------------------------------------

def test_to_fraction_basic():
    """Перевод «числа процента» в десятичную долю работает корректно."""
    assert calc.to_fraction(6.0) == 0.06
    assert calc.to_fraction(0) == 0.0
    assert calc.to_fraction(100) == 1.0


def test_to_fraction_none_raises():
    """Пустой процент — ошибка ValueError."""
    with pytest.raises(ValueError):
        calc.to_fraction(None)


def test_monthly_rate_from_annual_geometry():
    """Геометрическая конвертация годовой ставки в месячную обратима."""
    r = calc.monthly_rate_from_annual(12.0)
    expected = (1.12 ** (1 / 12)) - 1
    assert math.isclose(r, expected, rel_tol=1e-12)
    assert math.isclose(calc.annual_rate_from_monthly(r), 12.0, rel_tol=1e-9)


def test_months_to_years_and_days():
    """Перевод месяцев в годы/дни (1 мес = 30 дн)."""
    assert calc.months_to_years(24) == 2.0
    assert calc.months_to_days(2) == 60.0


# ---------------------------------------------------------------------------
# Расходы
# ---------------------------------------------------------------------------

def make_expense(monthly: float, include: bool = True, name: str = "X") -> calc.ExpenseRow:
    """Удобный конструктор ExpenseRow для тестов."""
    return calc.ExpenseRow(
        category1="cat",
        category2="sub",
        name=name,
        monthly_amount=monthly,
        unit="мес",
        include=include,
    )


def test_total_monthly_expenses_filters_inactive():
    """Сумма учитывает только строки с include=True."""
    rows = [
        make_expense(100, include=True, name="a"),
        make_expense(200, include=False, name="b"),
        make_expense(50, include=True, name="c"),
    ]
    assert calc.total_monthly_expenses(rows) == 150.0


def test_aggregate_by_category1():
    """Агрегация суммирует месячные суммы по категории 1."""
    rows = [
        calc.ExpenseRow("еда", "", "хлеб", 10, "", True),
        calc.ExpenseRow("еда", "", "молоко", 20, "", True),
        calc.ExpenseRow("транспорт", "", "метро", 5, "", True),
        calc.ExpenseRow("транспорт", "", "такси", 100, "", False),
    ]
    agg = calc.aggregate_by_category1(rows)
    assert dict(zip(agg["category1"], agg["amount"])) == {
        "еда": 30.0,
        "транспорт": 5.0,
    }


def test_expenses_for_pie_rolls_up_small():
    """Мелкие доли (<2%) схлопываются в «Прочее» для читаемости диаграммы."""
    rows = [make_expense(100, True, name=f"x{i}") for i in range(20)]
    rows.append(make_expense(50000, True, name="big"))
    pie = calc.expenses_for_pie(rows)
    assert "big" in pie["name"].tolist()
    assert "Прочее" in pie["name"].tolist()


# ---------------------------------------------------------------------------
# Портфель
# ---------------------------------------------------------------------------

def make_portfolio_row(
    weight: float, ret: float, tax: float = 0.0, fee: float = 0.0,
    name: str = "X",
) -> calc.PortfolioRow:
    """Удобный конструктор PortfolioRow для тестов."""
    return calc.PortfolioRow(
        asset_type=name,
        weight_percent=weight,
        expected_return_percent=ret,
        tax_percent=tax,
        fee_percent=fee,
    )


def test_portfolio_expected_return_weighted():
    """Ожидаемая доходность — взвешенное среднее."""
    rows = [
        make_portfolio_row(60, 10, name="A"),
        make_portfolio_row(40, 5, name="B"),
    ]
    # 0.6*10 + 0.4*5 = 8
    assert math.isclose(calc.portfolio_expected_return_percent(rows), 8.0)


def test_portfolio_after_costs_subtracts_tax_and_fee():
    """Net-доходность учитывает налог и комиссию по каждой строке."""
    rows = [
        make_portfolio_row(50, 10, tax=5, fee=0, name="A"),  # net = 10*0.95 = 9.5
        make_portfolio_row(50, 8, tax=0, fee=2, name="B"),   # net = 8 - 2 = 6
    ]
    # 0.5*9.5 + 0.5*6 = 7.75
    assert math.isclose(calc.portfolio_after_costs_percent(rows), 7.75)


def test_validate_weights_ok_and_fail():
    """Валидация весов: 100±0.5% — ок, иначе ошибка."""
    calc.validate_weights([
        make_portfolio_row(50, 5, name="A"),
        make_portfolio_row(50, 5, name="B"),
    ])
    with pytest.raises(ValueError):
        calc.validate_weights([
            make_portfolio_row(40, 5, name="A"),
            make_portfolio_row(40, 5, name="B"),
        ])


# ---------------------------------------------------------------------------
# Время достижения цели
# ---------------------------------------------------------------------------

def test_time_to_capital_already_done():
    """Если current >= target — срок 0, achievable=True."""
    r = calc.time_to_goal_capital(current_capital=1000, target_capital=500, annual_return_percent=10)
    assert r.achievable is True
    assert r.months == 0


def test_time_to_capital_target_zero():
    """Цель = 0 — тривиально достигнута."""
    r = calc.time_to_goal_capital(current_capital=100, target_capital=0, annual_return_percent=10)
    assert r.achievable is True
    assert r.months == 0


def test_time_to_capital_zero_return_unreachable():
    """Нулевая доходность + рост цели — недостижимо."""
    r = calc.time_to_goal_capital(current_capital=100, target_capital=200, annual_return_percent=0)
    assert r.achievable is False


def test_time_to_capital_negative_return_unreachable():
    """Отрицательная доходность — недостижимо (рост невозможен)."""
    r = calc.time_to_goal_capital(current_capital=100, target_capital=200, annual_return_percent=-5)
    assert r.achievable is False


def test_time_to_capital_value_geometry():
    """Удвоение капитала за 12% годовых = log(2)/log(1.12) лет."""
    r = calc.time_to_goal_capital(current_capital=100, target_capital=200, annual_return_percent=12)
    expected_years = math.log(2) / math.log(1.12)
    assert r.achievable
    assert math.isclose(r.years, expected_years, rel_tol=1e-9)
    assert math.isclose(r.months, expected_years * 12, rel_tol=1e-9)


def test_time_to_capital_no_capital_unreachable():
    """Капитал = 0 при росте цели — недостижимо."""
    r = calc.time_to_goal_capital(current_capital=0, target_capital=100, annual_return_percent=10)
    assert r.achievable is False


def test_time_to_income_zero_return_unreachable():
    """Пассивный доход не растёт при нулевой ставке — недостижимо."""
    r = calc.time_to_goal_income(current_capital=1_000_000, target_monthly_income=5000, annual_return_percent=0)
    assert r.achievable is False


def test_time_to_income_already_covered():
    """Если текущий пассивный доход покрывает цель — срок 0."""
    r = calc.time_to_goal_income(current_capital=10_000_000, target_monthly_income=1000, annual_return_percent=12)
    assert r.achievable is True
    assert r.months == 0


def test_time_to_income_value():
    """Аналитическое значение срока для пассивного дохода."""
    r_month = calc.monthly_rate_from_annual(12.0)
    expected_months = math.log(10000 / (1_000_000 * r_month)) / math.log(1 + r_month)
    r = calc.time_to_goal_income(
        current_capital=1_000_000, target_monthly_income=10_000, annual_return_percent=12,
    )
    assert r.achievable
    assert math.isclose(r.months, expected_months, rel_tol=1e-9)


def test_time_with_expenses_value():
    """Строгое аналитическое решение с учётом расходов."""
    capital = 100_000
    target = 200_000
    expenses = 10
    annual = 12.0
    r_month = (1.12) ** (1 / 12) - 1
    base = capital - expenses / r_month
    ratio = (target - expenses / r_month) / base
    expected_months = math.log(ratio) / math.log(1 + r_month)
    r = calc.time_to_goal_with_expenses(
        current_capital=capital,
        target_capital=target,
        annual_return_percent=annual,
        monthly_expenses=expenses,
    )
    assert r.achievable
    assert math.isclose(r.months, expected_months, rel_tol=1e-9)


def test_time_with_expenses_zero_expenses_equals_basic():
    """При нулевых расходах формула с расходами совпадает с базовой."""
    r_basic = calc.time_to_goal_capital(100_000, 200_000, 12.0)
    r_with = calc.time_to_goal_with_expenses(
        current_capital=100_000,
        target_capital=200_000,
        annual_return_percent=12.0,
        monthly_expenses=0.0,
    )
    assert r_basic.achievable and r_with.achievable
    assert math.isclose(r_basic.months, r_with.months, rel_tol=1e-9)


def test_time_with_expenses_exceeds_passive_unreachable():
    """Если расходы превышают пассивный доход — недостижимо."""
    r = calc.time_to_goal_with_expenses(
        current_capital=100_000,
        target_capital=200_000,
        annual_return_percent=1,
        monthly_expenses=10_000,
    )
    assert r.achievable is False


# ---------------------------------------------------------------------------
# Необходимый доход
# ---------------------------------------------------------------------------

def test_required_capital_for_income_value():
    """Капитал = target_monthly / r_month."""
    r_month = calc.monthly_rate_from_annual(12.0)
    expected = 10_000 / r_month
    assert math.isclose(calc.required_capital_for_income(10_000, 12.0), expected, rel_tol=1e-9)


def test_required_capital_for_income_zero_return_raises():
    """Нулевая доходность — ValueError (нет смысла считать)."""
    with pytest.raises(ValueError):
        calc.required_capital_for_income(1000, 0)


def test_required_monthly_income_value():
    """100 -> 200 за 6 лет: точное аналитическое значение."""
    res = calc.required_monthly_income(100, 200, 6)
    r_month = math.exp(math.log(2) / 72) - 1
    assert math.isclose(res["monthly_income"], 100 * r_month, rel_tol=1e-9)
    assert math.isclose(res["annual_return_percent"], ((1 + r_month) ** 12 - 1) * 100, rel_tol=1e-9)


def test_required_monthly_income_invalid():
    """Невалидные параметры (current<=0, target<=current, years<=0) — ValueError."""
    with pytest.raises(ValueError):
        calc.required_monthly_income(0, 100, 5)
    with pytest.raises(ValueError):
        calc.required_monthly_income(100, 50, 5)
    with pytest.raises(ValueError):
        calc.required_monthly_income(100, 200, 0)


# ---------------------------------------------------------------------------
# Аналитические функции
# ---------------------------------------------------------------------------

def test_time_vs_capital_dataframe():
    """Зависимость срока от капитала: больше капитал — меньше срок."""
    df = calc.time_vs_capital([100, 1000, 10000], target_capital=20000, annual_return_percent=10)
    assert list(df.columns) == ["capital", "years", "achievable"]
    assert bool(df.iloc[0]["achievable"]) is True
    assert df.iloc[-1]["years"] < df.iloc[0]["years"]


def test_time_vs_return_dataframe():
    """Зависимость срока от доходности; 0% — недостижимо."""
    df = calc.time_vs_return([1, 5, 10, 20], current_capital=100, target_capital=1000)
    assert list(df.columns) == ["return_percent", "years", "achievable"]
    df0 = calc.time_vs_return([0], current_capital=100, target_capital=1000)
    assert bool(df0.iloc[0]["achievable"]) is False


def test_time_vs_expenses_marks_unreachable():
    """Очень большие расходы помечаются как недостижимые."""
    df = calc.time_vs_expenses(
        [0, 10, 100000, 1_000_000],
        current_capital=100_000,
        target_capital=1_000_000,
        annual_return_percent=1,
    )
    assert bool(df.iloc[-1]["achievable"]) is False
    assert bool(df.iloc[0]["achievable"]) is True
