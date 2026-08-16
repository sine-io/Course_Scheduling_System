"""教师账号绑定与联系信息测试。对应 M2-0 验收标准。"""

import io
from uuid import uuid4

import pytest
from openpyxl import Workbook

from app.api.imports import XLSX_MIME
from app.models.user import Role, User
from app.services.teachers import current_teacher
from tests.conftest import make_user

PW = "password123"


@pytest.fixture
def sched(env):
    """已登录系统管理员 + 一个学期。返回 (client, semester_id, db)。"""
    client, db = env
    make_user(db, "s", PW, roles=[Role.admin])
    client.post("/api/auth/login", json={"username": "s", "password": PW})
    sem = client.post("/api/semesters", json={"academic_year": 2026, "term": 1}).json()
    return client, sem["id"], db


def _make_teacher_account(db, username: str) -> int:
    return make_user(db, username, PW, roles=[Role.teacher]).id


def _binding_body(sid: int, name: str, user_id: int, **fields) -> dict:
    return {
        "name": name,
        "user_id": user_id,
        "account_confirmation": {
            "operation_id": str(uuid4()),
            "confirmed": True,
            "target": f"teacher:{sid}:{name}:account:{user_id}",
        },
        **fields,
    }


# ── 联系信息 ──────────────────────────
def test_contact_fields_crud(sched):
    client, sid, _ = sched
    r = client.post(
        f"/api/teachers?semester_id={sid}",
        json={"name": "王老师", "email": "wang@example.edu.cn", "phone": "13812345678",
              "line_id": "wang_line"},
    )
    assert r.status_code == 201
    t = r.json()
    assert t["email"] == "wang@example.edu.cn"
    assert t["phone"] == "13812345678"
    assert t["line_id"] == "wang_line"
    # 更新联系信息
    r = client.patch(f"/api/teachers/{t['id']}", json={"name": "王老师", "email": "new@a.bc"})
    assert r.json()["email"] == "new@a.bc"
    assert r.json()["phone"] is None  # 未带入 → 清空


def test_invalid_email_rejected(sched):
    """验收④:Email 格式错误报告错误。"""
    client, sid, _ = sched
    r = client.post(
        f"/api/teachers?semester_id={sid}", json={"name": "王老师", "email": "not-an-email"}
    )
    assert r.status_code == 422


def test_empty_email_becomes_null(sched):
    client, sid, _ = sched
    r = client.post(f"/api/teachers?semester_id={sid}", json={"name": "王老师", "email": ""})
    assert r.status_code == 201
    assert r.json()["email"] is None


# ── 账号绑定 ──────────────────────────
def test_bind_account_success(sched):
    client, sid, db = sched
    uid = _make_teacher_account(db, "wang001")
    r = client.post(
        f"/api/teachers?semester_id={sid}",
        json=_binding_body(sid, "王老师", uid),
    )
    assert r.status_code == 201
    assert r.json()["user_id"] == uid


def test_bind_nonexistent_account_400(sched):
    client, sid, _ = sched
    r = client.post(
        f"/api/teachers?semester_id={sid}",
        json=_binding_body(sid, "王老师", 99999),
    )
    assert r.status_code == 400


def test_bind_same_account_twice_409(sched):
    """验收③:同账号在同学期绑第二位教师 → 409。"""
    client, sid, db = sched
    uid = _make_teacher_account(db, "wang001")
    assert client.post(
        f"/api/teachers?semester_id={sid}", json=_binding_body(sid, "王老师", uid)
    ).status_code == 201
    r = client.post(
        f"/api/teachers?semester_id={sid}",
        json=_binding_body(sid, "李老师", uid),
    )
    assert r.status_code == 409


def test_rebind_same_teacher_ok(sched):
    """同一教师重存自己已绑的账号不应被当成冲突。"""
    client, sid, db = sched
    uid = _make_teacher_account(db, "wang001")
    t = client.post(
        f"/api/teachers?semester_id={sid}", json=_binding_body(sid, "王老师", uid)
    ).json()
    r = client.patch(f"/api/teachers/{t['id']}", json={"name": "王老师", "user_id": uid})
    assert r.status_code == 200
    assert r.json()["user_id"] == uid


def test_bindable_accounts_excludes_bound(sched):
    client, sid, db = sched
    u1 = _make_teacher_account(db, "wang001")
    u2 = _make_teacher_account(db, "lee001")
    # 绑定 u1 给某教师
    client.post(
        f"/api/teachers?semester_id={sid}",
        json=_binding_body(sid, "王老师", u1),
    )
    avail = client.get(f"/api/teachers/bindable-accounts?semester_id={sid}").json()
    ids = {a["id"] for a in avail}
    assert u2 in ids and u1 not in ids


def test_bindable_accounts_includes_current_in_edit(sched):
    client, sid, db = sched
    u1 = _make_teacher_account(db, "wang001")
    t = client.post(
        f"/api/teachers?semester_id={sid}", json=_binding_body(sid, "王老师", u1)
    ).json()
    # 编辑场景:带 current_teacher_id → 应含目前绑定的 u1
    avail = client.get(
        f"/api/teachers/bindable-accounts?semester_id={sid}&current_teacher_id={t['id']}"
    ).json()
    assert u1 in {a["id"] for a in avail}


# ── current_teacher helper ──────────────
def test_current_teacher_helper(sched):
    client, sid, db = sched
    uid = _make_teacher_account(db, "wang001")
    client.post(
        f"/api/teachers?semester_id={sid}",
        json=_binding_body(sid, "王老师", uid),
    )
    user = db.get(User, uid)
    t = current_teacher(db, user, sid)
    assert t is not None and t.name == "王老师"
    # 未绑定学期回 None
    assert current_teacher(db, user, 99999) is None


# ── Excel 导入绑定 ──────────────────────
def _make_xlsx(rows: list[list], ncols: int) -> bytes:
    wb = Workbook()
    ws = wb.active
    for _ in range(3):
        ws.append(["表头"] * ncols)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload_teachers(client, sid, rows, ncols=11, create_accounts=True):
    content = _make_xlsx(rows, ncols)
    url = f"/api/import/teachers?semester_id={sid}"
    if create_accounts:
        url += "&create_accounts=true"
    data = None
    if create_accounts:
        data = {
            "operation_id": str(uuid4()),
            "confirmed": "true",
            "target": f"semester:{sid}:teacher-accounts",
        }
    return client.post(url, data=data, files={"file": ("t.xlsx", content, XLSX_MIME)})


def test_import_binds_account(sched):
    """验收①:导入教师勾创建账号 → user_id 正确绑定;含联系字段。"""
    client, sid, _ = sched
    rows = [
        ["王小明", "1234", "", 20, "", "", "否", "wang001", "wang@a.bc", "0911", "wl"],
        ["李小华", "5678", "", 18, "", "", "否", "lee001", "", "", ""],
    ]
    r = _upload_teachers(client, sid, rows)
    assert r.json()["imported"] == 2
    teachers = client.get(f"/api/teachers?semester_id={sid}").json()
    wang = next(t for t in teachers if t["name"] == "王小明")
    assert wang["user_id"] is not None
    assert wang["email"] == "wang@a.bc"
    assert wang["phone"] == "0911"
    # 绑定账号可用默认密码登录
    client.post("/api/auth/logout")
    login = client.post("/api/auth/login", json={"username": "wang001", "password": "changeme"})
    assert login.status_code == 200


def test_import_invalid_email_zero_write(sched):
    client, sid, _ = sched
    rows = [["王小明", "", "", "", "", "", "", "", "坏掉的email", "", ""]]
    body = _upload_teachers(client, sid, rows, create_accounts=False).json()
    assert body["imported"] == 0
    assert any("Email" in e for e in body["errors"])
    assert client.get(f"/api/teachers?semester_id={sid}").json() == []


# ── 开新学期复制保留绑定 ──────────────
def test_copy_preserves_binding_and_contact(sched):
    """验收②:复制后新学期教师仍绑同一账号、联系信息完整。"""
    client, sid, db = sched
    uid = _make_teacher_account(db, "wang001")
    client.post(
        f"/api/teachers?semester_id={sid}",
        json=_binding_body(
            sid,
            "王老师",
            uid,
            email="wang@a.bc",
            phone="0911",
        ),
    )
    r = client.post(
        f"/api/semesters/{sid}/copy",
        json={"academic_year": 2027, "term": 1, "grade_promotion": False},
    )
    assert r.status_code == 201
    nid = r.json()["id"]
    nt = client.get(f"/api/teachers?semester_id={nid}").json()[0]
    assert nt["user_id"] == uid
    assert nt["email"] == "wang@a.bc"
    assert nt["phone"] == "0911"
