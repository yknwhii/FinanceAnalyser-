"""
Создаёт тестовые файлы .env и Excel для ручной проверки CLI.
Запускать из корня проекта: python tests/e2e_make_data.py
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

from openpyxl import Workbook  # noqa: E402

# .env
(ROOT / ".env").write_text(
    "EXPENSES_FILE=./data/expenses.xlsx\n"
    "PORTFOLIO_FILE=./data/portfolio.xlsx\n"
    "INFLATION_PCT=6.0\n"
    "CURRENT_CAPITAL=1000000\n",
    encoding="utf-8",
)

# Excel расходов (без столбца «норма расхода на 1 ед.»)
data_dir = ROOT / "data"
data_dir.mkdir(exist_ok=True)
wb = Workbook()
ws = wb.active
ws.append([
    "категория 1", "категория 2", "наименование",
    "норма расхода на 1 мес", "единица измерения", "учитывать",
])
ws.append(["Жильё", "аренда", "квартира", 30000, "мес", True])
ws.append(["Еда", "бакалея", "хлеб/молоко", 12000, "мес", True])
ws.append(["Еда", "прочее", "прочее", 8000, "мес", True])
ws.append(["Транспорт", "метро", "метро", 3000, "мес", True])
ws.append(["Подписки", "прочее", "нетфликс", 900, "мес", True])
ws.append(["Прочее", "прочее", "мелочь", 500, "мес", False])
wb.save(data_dir / "expenses.xlsx")

# Excel портфеля
wb = Workbook()
ws = wb.active
ws.append(["Тип актива", "Доля портфеля", "% Ожидаемая доходность", "налог %", "комиссия %"])
ws.append(["Акции РФ", 40, 12, 5, 0])
ws.append(["Акции США", 30, 10, 5, 0.5])
ws.append(["Облигации", 20, 8, 0, 0.5])
ws.append(["Кэш", 10, 6, 0, 0])
wb.save(data_dir / "portfolio.xlsx")

print("Тестовые файлы созданы:")
print(f"  {ROOT / '.env'}")
print(f"  {data_dir / 'expenses.xlsx'}")
print(f"  {data_dir / 'portfolio.xlsx'}")
