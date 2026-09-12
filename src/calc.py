"""
calc.py
=======
Финансовое ядро приложения finance.

Содержит:
  * расчёт месячных расходов и их агрегацию;
  * расчёт ожидаемой доходности портфеля;
  * расчёт времени достижения финансовой цели;
  * расчёт необходимого дохода;
  * подготовку данных для аналитических графиков.

Все функции детерминированы и не зависят от CLI / ввода-вывода.

Единицы измерения и временные базы
-----------------------------------
* Расходы ............................... в месяц (месячная норма)
* Доходность портфеля .................... годовая номинальная, %
* Инфляция ............................... годовая, %
* Капитал/цели ........................... абсолютные денежные единицы
* Срок ................................... результат возвращается в
                                            днях/месяцах/годах

Формат процентов
----------------
Внутри функций проценты принимаются как «число процента»: 6.0 -> 6%.
Для перевода в долю используется _to_fraction().

Финансовая модель
-----------------
Считаем, что инвестор живёт на доход от текущего капитала (без внешних
пополнений). Месячная доходность пересчитывается из годовой геометрически:

    r_month = (1 + r_annual) ** (1/12) - 1

Месячный доход:
    income_month = capital * r_month
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Проценты и временные преобразования
# ---------------------------------------------------------------------------

def to_fraction(percent: float) -> float:
    """Перевод «числа процента» (6.0) в десятичную долю (0.06)."""
    if percent is None:
        raise ValueError("Процент не задан")
    return float(percent) / 100.0


def monthly_rate_from_annual(annual_percent: float) -> float:
    """Годовая номинальная % -> месячная десятичная доля (геометрическая)."""
    r = to_fraction(annual_percent)
    return (1.0 + r) ** (1.0 / 12.0) - 1.0


def annual_rate_from_monthly(monthly_fraction: float) -> float:
    """Месячная десятичная доля -> годовая номинальная % (геометрическая)."""
    return ((1.0 + monthly_fraction) ** 12 - 1.0) * 100.0


def months_to_years(months: float) -> float:
    """Месяцы -> годы (1 год = 12 месяцев)."""
    return months / 12.0


def months_to_days(months: float, days_per_month: int = 30) -> float:
    """Месяцы -> дни (1 месяц = 30 дней по умолчанию)."""
    return months * days_per_month


# ---------------------------------------------------------------------------
# Расходы
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExpenseRow:
    """Одна строка расходов после загрузки и валидации."""
    category1: str
    category2: str
    name: str
    monthly_amount: float
    unit: str
    include: bool


def filter_active(rows: Iterable[ExpenseRow]) -> list[ExpenseRow]:
    """Оставить только строки с флагом include=True (активные расходы)."""
    return [r for r in rows if r.include]


def total_monthly_expenses(rows: Iterable[ExpenseRow]) -> float:
    """Сумма месячных норм только по активным строкам."""
    return float(sum(r.monthly_amount for r in rows if r.include))


def aggregate_by_category1(rows: Iterable[ExpenseRow]) -> pd.DataFrame:
    """Агрегировать активные расходы по «категория 1» (для сводки)."""
    active = filter_active(rows)
    if not active:
        return pd.DataFrame(columns=["category1", "amount"])
    df = pd.DataFrame(active)
    out = (
        df.groupby("category1", as_index=False)["monthly_amount"]
        .sum()
        .rename(columns={"monthly_amount": "amount"})
        .sort_values("amount", ascending=False)
    )
    return out


def expenses_for_pie(rows: Iterable[ExpenseRow]) -> pd.DataFrame:
    """Данные для круговой диаграммы: мелкие доли (<2%) -> «Прочее»."""
    active = filter_active(rows)
    df = pd.DataFrame(active)
    if df.empty:
        return pd.DataFrame(columns=["name", "amount"])
    df = df[["name", "monthly_amount"]].rename(columns={"monthly_amount": "amount"})
    total = df["amount"].sum()
    if total <= 0:
        return df
    df["share"] = df["amount"] / total
    big = df[df["share"] >= 0.02].copy()
    small_sum = df.loc[df["share"] < 0.02, "amount"].sum()
    if small_sum > 0 and not big.empty:
        big = pd.concat(
            [big, pd.DataFrame([{"name": "Прочее", "amount": small_sum}])],
            ignore_index=True,
        )
    elif small_sum > 0 and big.empty:
        big = pd.DataFrame([{"name": "Прочее", "amount": small_sum}])
    return big[["name", "amount"]].sort_values("amount", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Портфель / доходы
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PortfolioRow:
    """Одна строка портфеля после загрузки и валидации."""
    asset_type: str
    weight_percent: float
    expected_return_percent: float
    tax_percent: float
    fee_percent: float


def validate_weights(rows: Sequence[PortfolioRow]) -> None:
    """Проверить, что суммарный вес портфеля близок к 100% (±0.5%)."""
    total = sum(r.weight_percent for r in rows)
    if not math.isclose(total, 100.0, abs_tol=0.5):
        raise ValueError(
            f"Сумма долей портфеля = {total:.2f}% (ожидается 100% ± 0.5%)"
        )


def portfolio_expected_return_percent(rows: Sequence[PortfolioRow]) -> float:
    """Взвешенная ожидаемая доходность портфеля (годовая, %, gross).

    Налоги/комиссии не вычитаются автоматически — пользователь задаёт
    уже чистую ожидаемую доходность. Net-вариант — см. ниже.
    """
    if not rows:
        raise ValueError("Портфель пуст")
    total_weight = sum(r.weight_percent for r in rows)
    if total_weight <= 0:
        raise ValueError("Сумма долей портфеля должна быть > 0")
    weighted = sum(
        (r.weight_percent / total_weight) * r.expected_return_percent for r in rows
    )
    return float(weighted)


def portfolio_after_costs_percent(rows: Sequence[PortfolioRow]) -> float:
    """Годовая доходность портфеля (%, net) с вычетом налога и комиссии."""
    if not rows:
        raise ValueError("Портфель пуст")
    total_weight = sum(r.weight_percent for r in rows)
    after = 0.0
    for r in rows:
        gross = r.expected_return_percent
        net = gross * (1.0 - to_fraction(r.tax_percent)) - r.fee_percent
        after += (r.weight_percent / total_weight) * net
    return float(after)


# ---------------------------------------------------------------------------
# Цели и сроки
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GoalResult:
    """Результат расчёта времени достижения финансовой цели."""
    months: float
    years: float
    days: float
    achievable: bool
    note: str

    def __str__(self) -> str:  # noqa: D401 - pretty print
        return (
            f"Срок: {self.years:.2f} лет "
            f"({self.months:.1f} мес., {self.days:.0f} дн.) — {self.note}"
        )


def _months_to_target_capital(
    capital: float,
    target: float,
    monthly_rate: float,
) -> float | None:
    """Месяцы до целевого капитала: n = log(target/capital)/log(1+r)."""
    if capital <= 0 or target <= 0:
        return None
    if target <= capital:
        return 0.0
    if monthly_rate <= 0:
        return None
    return math.log(target / capital) / math.log(1.0 + monthly_rate)


def _months_to_target_income(
    capital: float,
    target_monthly_income: float,
    monthly_rate: float,
) -> float | None:
    """Месяцы до целевого пассивного месячного дохода."""
    if capital <= 0 or target_monthly_income <= 0 or monthly_rate <= 0:
        return None
    current_income = capital * monthly_rate
    if current_income >= target_monthly_income:
        return 0.0
    ratio = target_monthly_income / (capital * monthly_rate)
    if ratio <= 1:
        return 0.0
    return math.log(ratio) / math.log(1.0 + monthly_rate)


def time_to_goal_capital(
    current_capital: float,
    target_capital: float,
    annual_return_percent: float,
) -> GoalResult:
    """Время достижения целевого капитала по годовой ставке."""
    if current_capital < 0 or target_capital < 0:
        return GoalResult(0, 0, 0, False, "капитал/цель не могут быть отрицательными")
    if target_capital == 0:
        return GoalResult(0, 0, 0, True, "цель = 0 (уже достигнута)")
    if current_capital >= target_capital:
        return GoalResult(0, 0, 0, True, "цель уже достигнута")
    if current_capital <= 0:
        return GoalResult(
            0, 0, 0, False,
            "недостаточный начальный капитал (нужен > 0)",
        )
    r_month = monthly_rate_from_annual(annual_return_percent)
    if r_month <= 0:
        return GoalResult(
            0, 0, 0, False,
            "нулевая/отрицательная доходность — рост капитала невозможен",
        )
    months = _months_to_target_capital(current_capital, target_capital, r_month)
    if months is None:
        return GoalResult(0, 0, 0, False, "недостижимо при данной доходности")
    if not math.isfinite(months):
        return GoalResult(0, 0, 0, False, "недостижимо (бесконечный срок)")
    return GoalResult(
        months=months,
        years=months_to_years(months),
        days=months_to_days(months),
        achievable=True,
        note="рост капитала по годовой ставке",
    )


def time_to_goal_income(
    current_capital: float,
    target_monthly_income: float,
    annual_return_percent: float,
) -> GoalResult:
    """Время достижения целевого пассивного месячного дохода."""
    if current_capital < 0 or target_monthly_income < 0:
        return GoalResult(0, 0, 0, False, "капитал/цель не могут быть отрицательными")
    if target_monthly_income == 0:
        return GoalResult(0, 0, 0, True, "целевой доход = 0 (уже достигнут)")

    r_month = monthly_rate_from_annual(annual_return_percent)
    if r_month <= 0:
        return GoalResult(
            0, 0, 0, False,
            "нулевая/отрицательная доходность — пассивный доход не растёт",
        )
    if current_capital <= 0:
        return GoalResult(
            0, 0, 0, False,
            "недостаточный начальный капитал (нужен > 0)",
        )
    months = _months_to_target_income(current_capital, target_monthly_income, r_month)
    if months is None:
        return GoalResult(0, 0, 0, False, "недостижимо при данной доходности")
    if not math.isfinite(months):
        return GoalResult(0, 0, 0, False, "недостижимо (бесконечный срок)")
    return GoalResult(
        months=months,
        years=months_to_years(months),
        days=months_to_days(months),
        achievable=True,
        note="рост пассивного месячного дохода",
    )


def time_to_goal_with_expenses(
    current_capital: float,
    target_capital: float,
    annual_return_percent: float,
    monthly_expenses: float,
) -> GoalResult:
    """Время достижения цели с учётом месячных расходов.

    Модель: пассивный доход C·r уменьшается на расходы E ежемесячно.
    C(n) = (C₀ − E/r)·(1+r)ⁿ + E/r; решаем относительно n.
    """
    if current_capital < 0 or target_capital < 0 or monthly_expenses < 0:
        return GoalResult(0, 0, 0, False, "отрицательные параметры недопустимы")
    if target_capital == 0:
        return GoalResult(0, 0, 0, True, "цель = 0 (уже достигнута)")
    if current_capital >= target_capital:
        return GoalResult(0, 0, 0, True, "цель уже достигнута")
    if current_capital <= 0:
        return GoalResult(
            0, 0, 0, False,
            "недостаточный начальный капитал (нужен > 0)",
        )

    r_month = monthly_rate_from_annual(annual_return_percent)
    expenses = float(monthly_expenses)

    if r_month <= 0:
        return GoalResult(
            0, 0, 0, False,
            "нулевая/отрицательная доходность — рост невозможен",
        )

    base = current_capital - expenses / r_month
    if base <= 0:
        return GoalResult(
            0, 0, 0, False,
            "расходы превышают пассивный доход — капитал будет уменьшаться",
        )

    ratio = (target_capital - expenses / r_month) / base
    if ratio <= 1:
        return GoalResult(0, 0, 0, True, "цель уже достигнута с учётом расходов")
    months = math.log(ratio) / math.log(1.0 + r_month)
    if not math.isfinite(months):
        return GoalResult(0, 0, 0, False, "недостижимо (бесконечный срок)")
    return GoalResult(
        months=months,
        years=months_to_years(months),
        days=months_to_days(months),
        achievable=True,
        note="рост капитала с учётом месячных расходов",
    )


# ---------------------------------------------------------------------------
# Необходимый доход
# ---------------------------------------------------------------------------

def required_capital_for_income(
    target_monthly_income: float,
    annual_return_percent: float,
) -> float:
    """Капитал, при котором пассивный месячный доход = target."""
    if target_monthly_income < 0:
        raise ValueError("целевой доход не может быть отрицательным")
    r_month = monthly_rate_from_annual(annual_return_percent)
    if r_month <= 0:
        raise ValueError("доходность должна быть > 0")
    return target_monthly_income / r_month


def required_monthly_income(
    current_capital: float,
    target_capital: float,
    years: float,
) -> dict:
    """Ежемесячный доход, чтобы за N лет пройти от current к target.

    Возвращает {'monthly_income', 'annual_return_percent'}.
    """
    if current_capital <= 0 or target_capital <= current_capital:
        raise ValueError("нужно current_capital > 0 и target > current")
    if years <= 0:
        raise ValueError("years должно быть > 0")
    months = years * 12.0
    r_month = math.exp(math.log(target_capital / current_capital) / months) - 1.0
    if r_month <= 0:
        raise ValueError("полученная доходность <= 0 — параметры несовместимы")
    annual_pct = annual_rate_from_monthly(r_month)
    monthly_income = current_capital * r_month
    return {
        "monthly_income": float(monthly_income),
        "annual_return_percent": float(annual_pct),
    }


# ---------------------------------------------------------------------------
# Аналитика: зависимости времени достижения цели от параметров
# ---------------------------------------------------------------------------

def time_vs_capital(
    capital_values: Sequence[float],
    target_capital: float,
    annual_return_percent: float,
) -> pd.DataFrame:
    """Срок (в годах) до цели в зависимости от начального капитала."""
    rows = []
    for c in capital_values:
        res = time_to_goal_capital(float(c), target_capital, annual_return_percent)
        rows.append(
            {
                "capital": float(c),
                "years": res.years if res.achievable else np.nan,
                "achievable": res.achievable,
            }
        )
    return pd.DataFrame(rows)


def time_vs_return(
    return_values_percent: Sequence[float],
    current_capital: float,
    target_capital: float,
) -> pd.DataFrame:
    """Срок (в годах) до цели в зависимости от годовой доходности."""
    rows = []
    for r in return_values_percent:
        res = time_to_goal_capital(current_capital, target_capital, float(r))
        rows.append(
            {
                "return_percent": float(r),
                "years": res.years if res.achievable else np.nan,
                "achievable": res.achievable,
            }
        )
    return pd.DataFrame(rows)


def time_vs_expenses(
    expense_values: Sequence[float],
    current_capital: float,
    target_capital: float,
    annual_return_percent: float,
) -> pd.DataFrame:
    """Срок до цели в зависимости от месячных расходов."""
    rows = []
    for e in expense_values:
        res = time_to_goal_with_expenses(
            current_capital, target_capital, annual_return_percent, float(e),
        )
        rows.append(
            {
                "monthly_expenses": float(e),
                "years": res.years if res.achievable else np.nan,
                "achievable": res.achievable,
            }
        )
    return pd.DataFrame(rows)
