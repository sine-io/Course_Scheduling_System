"""三套学制验证数据集(tasks.md 测试策略总则第 1 点,整个项目共用)。

- `build_elementary_small`   小学 6 班(包班+任课教师、周三下午空、班主任时间)
- `build_junior_high_mid`    初中 12 班(学科课程+弹性课程+兼行政减课教师)
- `build_vocational_high`    中职 15 班 3 科(3 连堂实习+实训室+企业兼职教师+走班群组)

三套数据均已于 `tests/test_fixtures.py` 验证自洽(无超课时、班级节数不超可排格数、
教室/场地需求不超供给、走班群组成员同作息时间表),可直接喂给 M3 排课引擎。
"""

from ._common import Builder, Fixture, room_demand, teacher_available_slots
from .elementary import build_elementary_small
from .junior_high import build_junior_high_mid
from .scale import build_large_school
from .vocational import build_vocational_high

__all__ = [
    "Builder",
    "Fixture",
    "build_elementary_small",
    "build_junior_high_mid",
    "build_large_school",
    "build_vocational_high",
    "room_demand",
    "teacher_available_slots",
]
