"""elementary_small:小学 6 班(一~六年级各一班)。

特征(tasks.md 测试策略总则):
- **包班**：班主任承担本班语文、数学、生活（低年级）或科学、道德与法治（中高年级）及综合实践活动
- **任课教师**：英语、艺术、体育与健康由专任教师跨班任教
- **周三下午空**:来自小学测试作息(周三第 5–7 节为 reserved)
- **班主任时间**:周五第七节改为班主任时间(不排课)

可排格数 31(每日 7 节一般课 × 5 天 − 周三下午 3 节 − 周五班主任时间 1 节)。
"""

from sqlalchemy.orm import Session

from app.models.basedata import ClassTrack, RoomType
from app.models.period import PeriodType

from ._common import Builder, Fixture

# 每班每周节数:低年级 23 节、中高年级 28 节(均 ≤ 31 可排格数)
LOWER_GRADES = (1, 2)

# 班主任包班科目 → 节数
HOMEROOM_LOWER = {"语文": 6, "数学": 4, "生活": 6, "综合实践活动": 2}
HOMEROOM_UPPER = {"语文": 6, "数学": 4, "科学": 3, "道德与法治": 3, "综合实践活动": 3}

CLASS_NAMES = {
    1: "一年甲班",
    2: "二年甲班",
    3: "三年甲班",
    4: "四年甲班",
    5: "五年甲班",
    6: "六年甲班",
}
HOMEROOM_TEACHERS = {
    1: "林淑芬",
    2: "陈美玲",
    3: "王雅婷",
    4: "张怡君",
    5: "李佳蓉",
    6: "黄志伟",
}


def build_elementary_small(db: Session, academic_year: int = 2026, term: int = 1) -> Fixture:
    b = Builder(db, academic_year, term, "elementary")

    # 周五第七节改为班主任时间(周三下午已由模板标为 reserved)
    b.set_period(weekday=5, period_no=9, ptype=PeriodType.homeroom, name="班主任时间")

    b.subject("艺术", required_room_type=RoomType.special)
    b.subject("体育与健康", required_room_type=RoomType.outdoor)

    # 班主任:小学班主任基本课时 22 节,包班 18–19 节
    for grade, name in HOMEROOM_TEACHERS.items():
        b.teacher(name, base_periods=22)
        b.klass(
            CLASS_NAMES[grade],
            grade=grade,
            track=ClassTrack.elementary.value,
            student_count=26,
            homeroom=name,
        )

    # 任课教师
    b.teacher("吴英杰", base_periods=20, subjects=["英语", "地方课程"])  # 16 节
    b.teacher("蔡文玲", base_periods=20, subjects=["艺术"])            # 12 节
    b.teacher("郑建宏", base_periods=20, subjects=["体育与健康"])       # 18 节

    b.room("音乐教室", room_type=RoomType.special, capacity=35, subjects=["艺术"])
    b.room("操场", room_type=RoomType.outdoor, capacity=120, subjects=["体育与健康"])
    for name in CLASS_NAMES.values():
        b.room(f"{name}教室", room_type=RoomType.normal, capacity=32)

    for grade, cname in CLASS_NAMES.items():
        lower = grade in LOWER_GRADES
        homeroom = HOMEROOM_TEACHERS[grade]

        for subject, periods in (HOMEROOM_LOWER if lower else HOMEROOM_UPPER).items():
            b.assign(subject=subject, teachers=[homeroom], periods=periods, classes=[cname])

        b.assign(subject="英语", teachers=["吴英杰"], periods=1 if lower else 2, classes=[cname])
        b.assign(subject="地方课程", teachers=["吴英杰"], periods=1, classes=[cname])
        b.assign(
            subject="体育与健康",
            teachers=["郑建宏"],
            periods=3,
            classes=[cname],
            room="操场",
            required_room_type=RoomType.outdoor,
            lock_room=True,
        )
        if not lower:  # 低年级的艺术涵盖于「生活」课程
            b.assign(
                subject="艺术",
                teachers=["蔡文玲"],
                periods=3,
                classes=[cname],
                room="音乐教室",
                required_room_type=RoomType.special,
                lock_room=True,
            )

    return b.build()
