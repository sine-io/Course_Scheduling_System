"""M4-2:代课推荐、指派处理方式、调课验证。

**推荐引擎是这张卡的星角**,测试也集中在它:排序规则(同科目 > 当天在校 > 本月代课少)
与硬性过滤(那个特定日期真的能来的人)。

硬性过滤正是 Fable 5 提醒的「周格 vs 特定日期」落差——李师周三第二节空堂,
不代表 11/11 他能代(他自己可能也请假、或已被指派代别班)。这里逐一造出那些场景。
"""

from datetime import date

import pytest

from app.models.leave import AffectedPeriod, AffectedStatus
from app.models.user import Role
from tests.api_helpers import create_api_semester
from tests.conftest import make_user
from tests.dates import SEM_END, SEM_START, WED, WED2  # 日期统一由执行当日推算,不硬编

PW = "password123"


@pytest.fixture
def env2(env):
    """已发布课表的初中。返回 helper 对象,测试逐步叠教师/教学任务/请假。"""
    client, db = env
    make_user(db, "s", PW, roles=[Role.scheduler])
    client.post("/api/auth/login", json={"username": "s", "password": PW})
    sid = create_api_semester(
        client,
        ready=True,
        start_date=SEM_START.isoformat(),
        end_date=SEM_END.isoformat(),
    )["id"]
    return _World(client, db, sid)


class _World:
    def __init__(self, client, db, sid):
        self.client, self.db, self.sid = client, db, sid
        self.q = f"?semester_id={sid}"
        self.subjects: dict[str, int] = {
            s["name"]: s["id"]
            for s in client.get(f"/api/subjects{self.q}").json()
        }
        self.teachers: dict[str, int] = {}
        self.classes: dict[str, int] = {}
        self.tt = client.post(f"/api/timetables{self.q}", json={"name": "草稿A"}).json()["id"]
        self._published = False
        # 周三节次
        c = self.klass("900")  # 占位班,取作息时间表
        self.wed = [p for p in client.get(f"/api/class-units/{c}/period-table").json()["periods"]
                    if p["weekday"] == 3 and p["type"] == "regular"]

    def subject(self, name: str) -> int:
        if name not in self.subjects:
            self.subjects[name] = self.client.post(
                f"/api/subjects{self.q}", json={"name": name}).json()["id"]
        return self.subjects[name]

    def teacher(self, name: str, subjects: list[str] | None = None) -> int:
        tid = self.client.post(f"/api/teachers{self.q}", json={
            "name": name, "base_periods": 20,
            "subject_ids": [self.subject(s) for s in (subjects or [])],
        }).json()["id"]
        self.teachers[name] = tid
        return tid

    def klass(self, name: str) -> int:
        if name not in self.classes:
            self.classes[name] = self.client.post(f"/api/class-units{self.q}", json={
                "grade": 7, "name": name, "track": "junior_high"}).json()["id"]
        return self.classes[name]

    def place(self, teacher: str, subject: str, klass: str, period_idx: int, weekday: int = 3):
        """把 teacher 的 subject 课排到 (weekday, 第 period_idx 个一般课节次)、上 klass 班。"""
        slots = [p for p in self.client.get(
            f"/api/class-units/{self.klass(klass)}/period-table").json()["periods"]
            if p["weekday"] == weekday and p["type"] == "regular"]
        a = self.client.post(f"/api/assignments{self.q}", json={
            "class_id": self.klass(klass), "subject_id": self.subject(subject),
            "periods_per_week": 1, "teachers": [{"teacher_id": self.teachers[teacher]}],
            "block_rules": [],
        }).json()
        r = self.client.post(f"/api/timetables/{self.tt}/entries", json={
            "course_assignment_id": a["id"], "weekday": weekday,
            "period_no": slots[period_idx]["period_no"], "span": 1})
        assert r.status_code == 201, r.json()
        return a["id"], slots[period_idx]["period_no"]

    def publish(self):
        r = self.client.post(f"/api/timetables/{self.tt}/publish?force=true")
        assert r.status_code == 200, r.json()
        self._published = True

    def leave(self, teacher: str, when: date = WED) -> list[dict]:
        r = self.client.post(f"/api/leaves{self.q}", json={
            "teacher_id": self.teachers[teacher], "leave_type": "sick",
            "start_date": when.isoformat(), "end_date": when.isoformat()})
        assert r.status_code == 201, r.json()
        return r.json()["affected_periods"]

    def recommend(self, affected_id: int) -> dict:
        return self.client.get(
            f"/api/affected-periods/{affected_id}/recommendations").json()

    def assign(self, affected_id: int, **body) -> "tuple[int, dict]":
        r = self.client.put(f"/api/affected-periods/{affected_id}/substitution", json=body)
        return r.status_code, r.json()


# ── 验收①:第一名必为空堂 + 同科;已满档者靠后 ──────────────
def test_recommendation_ranks_same_subject_first(env2):
    w = env2
    w.teacher("王师", ["语文"])
    w.teacher("陈师", ["语文"])   # 同科,当天没课
    w.teacher("林师", ["数学"])   # 非本科
    # 王师周三第一节上 701 语文;陈师与林师该节空堂
    a_id, _ = w.place("王师", "语文", "701", 0)
    w.publish()
    affected = w.leave("王师")

    rec = w.recommend(affected[0]["id"])
    names = [c["teacher_name"] for c in rec["candidates"]]
    assert names[0] == "陈师", names   # 同科优先
    top = rec["candidates"][0]
    assert top["same_subject"] is True
    assert "同科目教师" in top["reasons"]


def test_at_school_that_day_beats_a_teacher_not_coming_in(env2):
    """同为非本科,当天已在校者优先(免多跑一趟)。"""
    w = env2
    w.teacher("王师", ["语文"])
    w.teacher("陈师", ["体育"])  # 非本科,当天周三另有课 → 已在校
    w.teacher("林师", ["体育"])  # 非本科,周三完全没课
    w.place("王师", "语文", "701", 0)  # 王师周三第一节(被请假)
    w.place("陈师", "体育", "702", 2)  # 陈师周三第三节有课 → 当天在校,但第一节空
    w.publish()
    affected = w.leave("王师")

    rec = w.recommend(affected[0]["id"])
    names = [c["teacher_name"] for c in rec["candidates"]]
    assert names.index("陈师") < names.index("林师"), names
    chen = next(c for c in rec["candidates"] if c["teacher_name"] == "陈师")
    assert chen["at_school_that_day"] is True
    assert "当天已在校" in chen["reasons"]


def test_fewer_monthly_sub_periods_ranks_higher(env2):
    """同科同条件时,本月代课少者优先(公平)。"""
    w = env2
    w.teacher("王师", ["语文"])
    w.teacher("陈师", ["语文"])
    w.teacher("林师", ["语文"])
    w.place("王师", "语文", "701", 0)
    # 林师本月已代一节(11/18):先帮另一个请假的老师代
    w.teacher("周师", ["语文"])
    w.place("周师", "语文", "702", 0, weekday=3)
    w.publish()

    other = w.client.post(f"/api/leaves{w.q}", json={
        "teacher_id": w.teachers["周师"], "leave_type": "sick",
        "start_date": WED2.isoformat(), "end_date": WED2.isoformat()}).json()
    code, _ = w.assign(other["affected_periods"][0]["id"],
                       type="substitute", handler_teacher_id=w.teachers["林师"])
    assert code == 200

    affected = w.leave("王师")  # 11/11
    rec = w.recommend(affected[0]["id"])
    names = [c["teacher_name"] for c in rec["candidates"] if c["teacher_name"] in ("陈师", "林师")]
    assert names[0] == "陈师", names  # 陈师本月 0 节,林师 1 节
    lin = next(c for c in rec["candidates"] if c["teacher_name"] == "林师")
    assert lin["sub_periods_this_month"] == 1
    assert "本月已代 1 节" in lin["reasons"]


# ── 硬性过滤:周格 vs 特定日期(Fable 5 的落差)──────────────
def test_a_teacher_busy_that_period_is_filtered_out(env2):
    """周格层:陈师该节有自己的课 → 不可代。"""
    w = env2
    w.teacher("王师", ["语文"])
    w.teacher("陈师", ["语文"])
    w.place("王师", "语文", "701", 0)  # 王师周三第一节
    w.place("陈师", "语文", "702", 0)  # 陈师同一节也有课
    w.publish()
    affected = w.leave("王师")

    names = [c["teacher_name"] for c in w.recommend(affected[0]["id"])["candidates"]]
    assert "陈师" not in names


def test_a_teacher_on_leave_that_day_is_filtered_out(env2):
    """日期层:陈师该节空堂,但『那一天』他自己也请假 → 不可代。"""
    w = env2
    w.teacher("王师", ["语文"])
    w.teacher("陈师", ["语文"])
    w.place("王师", "语文", "701", 0)   # 王师周三第一节(被请假)
    w.place("陈师", "语文", "703", 2)   # 陈师周三第三节有课;第一节空堂
    w.publish()
    w.leave("陈师")                     # 陈师也请全天假(含第一节)
    affected = w.leave("王师")

    names = [c["teacher_name"] for c in w.recommend(affected[0]["id"])["candidates"]]
    assert "陈师" not in names, "当天请假的人不该出现在可代列表"


def test_a_teacher_already_covering_that_slot_is_filtered_out(env2):
    """日期层:陈师该节空堂、当天没请假,但已被指派代别班 → 不可代。"""
    w = env2
    w.teacher("王师", ["语文"])
    w.teacher("周师", ["语文"])
    w.teacher("陈师", ["语文"])
    w.place("王师", "语文", "701", 0)  # 王师周三第一节
    w.place("周师", "语文", "702", 0)  # 周师同一节也有课(也会被请假)
    w.publish()

    a_wang = w.leave("王师")[0]["id"]
    a_zhou = w.leave("周师")[0]["id"]
    # 陈师先被指派去代周师那一节(周三第一节)
    code, _ = w.assign(a_zhou, type="substitute", handler_teacher_id=w.teachers["陈师"])
    assert code == 200

    names = [c["teacher_name"] for c in w.recommend(a_wang)["candidates"]]
    assert "陈师" not in names, "同一时段已被指派代课的人不该再被推荐"


def test_the_absent_teacher_is_never_a_candidate(env2):
    w = env2
    w.teacher("王师", ["语文"])
    w.place("王师", "语文", "701", 0)
    w.publish()
    affected = w.leave("王师")
    names = [c["teacher_name"] for c in w.recommend(affected[0]["id"])["candidates"]]
    assert "王师" not in names


# ── 验收③:全校无人可代 → 提示合班/自习 ────────────────────
def test_no_available_teacher_hints_merge_or_self_study(env2):
    w = env2
    w.teacher("王师", ["语文"])
    w.teacher("陈师", ["语文"])
    w.place("王师", "语文", "701", 0)  # 王师周三第一节
    w.place("陈师", "语文", "702", 0)  # 唯一其他教师同一节也有课
    w.publish()
    affected = w.leave("王师")

    rec = w.recommend(affected[0]["id"])
    assert rec["candidates"] == []
    assert "合班" in rec["no_candidate_hint"] and "自习" in rec["no_candidate_hint"]


# ── 指派处理方式 ─────────────────────────────────────────────────
def test_assigning_a_substitute_marks_resolved_and_notifies(env2):
    w = env2
    w.teacher("王师", ["语文"])
    w.teacher("陈师", ["语文"])
    w.place("王师", "语文", "701", 0)
    w.publish()
    affected_id = w.leave("王师")[0]["id"]

    code, body = w.assign(affected_id, type="substitute", handler_teacher_id=w.teachers["陈师"])
    assert code == 200
    assert body["type_label"] == "代课"
    assert body["handler_name"] == "陈师"
    assert body["counts_toward_hours"] is True

    ap = w.db.get(AffectedPeriod, affected_id)
    assert ap.status == AffectedStatus.resolved.value
    assert ap.handler_teacher_id == w.teachers["陈师"]

    # 陈师收到代课通知
    notes = w.client.get(
        f"/api/notifications{w.q}&teacher_id={w.teachers['陈师']}").json()
    assert notes and notes[0]["type"] == "substitution_assigned"


def test_self_study_and_merge_hours_policy(env2):
    """自习不计课时且无处理教师;合班计不计由默认(不计)。"""
    w = env2
    w.teacher("王师", ["语文"])
    w.teacher("陈师", ["语文"])
    w.place("王师", "语文", "701", 0)
    w.publish()
    ids = [p["id"] for p in w.leave("王师")]

    _, self_study = w.assign(ids[0], type="self_study")
    assert self_study["handler_name"] is None
    assert self_study["counts_toward_hours"] is False


def test_cannot_assign_absent_teacher_to_cover_self(env2):
    w = env2
    w.teacher("王师", ["语文"])
    w.place("王师", "语文", "701", 0)
    w.publish()
    affected_id = w.leave("王师")[0]["id"]
    code, body = w.assign(affected_id, type="substitute", handler_teacher_id=w.teachers["王师"])
    assert code == 409
    assert "代自己" in body["detail"]


def test_assigning_a_busy_teacher_is_rejected_with_reason(env2):
    w = env2
    w.teacher("王师", ["语文"])
    w.teacher("陈师", ["语文"])
    w.place("王师", "语文", "701", 0)
    w.place("陈师", "语文", "702", 0)  # 陈师同一节有课
    w.publish()
    affected_id = w.leave("王师")[0]["id"]
    code, body = w.assign(affected_id, type="substitute", handler_teacher_id=w.teachers["陈师"])
    assert code == 409
    assert "有自己的课" in body["detail"]


def test_clearing_a_substitution_returns_to_pending(env2):
    w = env2
    w.teacher("王师", ["语文"])
    w.teacher("陈师", ["语文"])
    w.place("王师", "语文", "701", 0)
    w.publish()
    affected_id = w.leave("王师")[0]["id"]
    w.assign(affected_id, type="substitute", handler_teacher_id=w.teachers["陈师"])

    r = w.client.delete(f"/api/affected-periods/{affected_id}/substitution")
    assert r.status_code == 200
    assert r.json()["status"] == AffectedStatus.pending.value
    assert w.db.get(AffectedPeriod, affected_id).handler_teacher_id is None
    # 陈师收到取消通知
    types = [n["type"] for n in w.client.get(
        f"/api/notifications{w.q}&teacher_id={w.teachers['陈师']}").json()]
    assert "substitution_cancelled" in types


# ── 验收②:调课(swap)验证 ─────────────────────────────────
def test_swap_succeeds_when_both_sides_are_free(env2):
    """乙代甲周三第一节;甲于下周三补乙原本周三第二节的课。两边都空 → 成立。"""
    w = env2
    w.teacher("王师", ["语文"])
    w.teacher("陈师", ["数学"])
    w.place("王师", "语文", "701", 0)              # 甲:周三第一节(被请假)
    _, swap_entry = _entry(w, "陈师", "数学", "702", 1)  # 乙:周三第二节
    w.publish()
    affected_id = w.leave("王师")[0]["id"]

    entry_id = _find_entry(w, "陈师")
    code, body = w.assign(
        affected_id, type="swap", handler_teacher_id=w.teachers["陈师"],
        swap_entry_id=entry_id, swap_date=WED2.isoformat())  # 下周三补
    assert code == 200, body
    assert body["type_label"] == "调课"
    assert body["swap_subject_name"] == "数学"
    assert body["swap_date"] == WED2.isoformat()


def test_swap_rejected_when_partner_busy_at_absent_slot(env2):
    """乙在甲请假那节本来就有课 → 无法来代,拒绝并指名。"""
    w = env2
    w.teacher("王师", ["语文"])
    w.teacher("陈师", ["数学"])
    w.place("王师", "语文", "701", 0)   # 甲周三第一节
    w.place("陈师", "数学", "702", 0)   # 乙周三第一节也有课
    _entry(w, "陈师", "数学", "703", 1)  # 乙另有周三第二节(用来当 swap 目标)
    w.publish()
    affected_id = w.leave("王师")[0]["id"]

    entry_id = _find_entry(w, "陈师", period_idx=1)
    code, body = w.assign(
        affected_id, type="swap", handler_teacher_id=w.teachers["陈师"],
        swap_entry_id=entry_id, swap_date=WED2.isoformat())
    assert code == 409
    assert "陈师" in body["detail"] and "有自己的课" in body["detail"]


def test_swap_rejected_when_absent_teacher_busy_at_makeup_slot(env2):
    """甲在补课那节本来就有别的课 → 补不了,拒绝并指名。"""
    w = env2
    w.teacher("王师", ["语文"])
    w.teacher("陈师", ["数学"])
    w.place("王师", "语文", "701", 0)   # 甲周三第一节(被请假)
    w.place("王师", "语文", "705", 1)   # 甲周三第二节另有课(补课会撞)
    _entry(w, "陈师", "数学", "702", 1)  # 乙周三第二节 → swap 目标
    w.publish()
    affected_id = [p for p in w.leave("王师") if p["period_name"] == w.wed[0]["name"]][0]["id"]

    entry_id = _find_entry(w, "陈师", period_idx=1)
    code, body = w.assign(
        affected_id, type="swap", handler_teacher_id=w.teachers["陈师"],
        swap_entry_id=entry_id, swap_date=WED2.isoformat())
    assert code == 409
    assert "王师" in body["detail"]


def _entry(w, teacher, subject, klass, period_idx):
    return w.place(teacher, subject, klass, period_idx)


def _find_entry(w, teacher: str, period_idx: int | None = None) -> int:
    """取某教师某节的 schedule_entry id(供 swap 目标)。"""
    from app.models.assignment import AssignmentTeacher, CourseAssignment
    from app.models.timetable import ScheduleEntry
    q = (w.db.query(ScheduleEntry)
         .join(CourseAssignment, ScheduleEntry.course_assignment_id == CourseAssignment.id)
         .join(AssignmentTeacher,
               AssignmentTeacher.course_assignment_id == CourseAssignment.id)
         .filter(AssignmentTeacher.teacher_id == w.teachers[teacher],
                 ScheduleEntry.timetable_id == w.tt))
    if period_idx is not None:
        q = q.filter(ScheduleEntry.period_no == w.wed[period_idx]["period_no"])
    return q.first().id
