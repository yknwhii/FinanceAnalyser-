"""
End-to-end прогон CLI: подменяем input() и проверяем, что все
основные сценарии отрабатывают без исключений.

ВНИМАНИЕ: графики выводятся через plt.show() и блокируют поток до
закрытия окна. Поэтому здесь мы НЕ вызываем пункты 5/6/7 —
только пункты, которые не требуют интерактивного окна.
"""

import builtins
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

import main  # noqa: E402

# Сценарий ввода пользователя:
# 1 - показать расходы
# 2 - портфель
# 3 - время достижения цели (5000000, 8)
# 4 - необходимый доход (1, "", 50000)
# 0 - выход
inputs = iter([
    "1",
    "2",
    "3", "5000000", "8",
    "4", "1", "", "50000",
    "0",
])
real_input = builtins.input
builtins.input = lambda prompt="": next(inputs)

try:
    state = main.State(config=main.load_config())
    main.bootstrap(state)
    rc = main.run(state)
    print(f"\nCLI завершился с кодом: {rc}")
finally:
    builtins.input = real_input
