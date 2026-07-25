"""Excel 导入测试。对应 M1-3 验收标准。"""

import io

import pytest
from openpyxl import Workbook

from app.api.imports import XLSX_MIME
from app.models.user import Role
from tests.conftest import make_user

PW = "password123"


@pytest.fixture
def scheduler_env(env):
    client, db = env
    make_user(db, "s", PW, roles=[Role.scheduler])
    client.post("/api/auth/login", json={"username": "s", "password": PW})
    sem = client.post("/api/semesters", json={"academic_year": 2026, "term": 1}).json()
    return client, sem["id"]


def make_xlsx(data_rows: list[list], ncols: int = 8) -> bytes:
    """创建含 3 行表头(字段名/说明/示例)+ 数据行的 xlsx。"""
    wb = Workbook()
    ws = wb.active
    ws.append(["字段名"] * ncols)
    ws.append(["说明"] * ncols)
    ws.append(["示例"] * ncols)
    for r in data_rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def upload(client, entity, sid, data_rows, ncols=8, create_accounts=False):
    content = make_xlsx(data_rows, ncols)
    url = f"/api/import/{entity}?semester_id={sid}"
    if create_accounts:
        url += "&create_accounts=true"
    return client.post(url, files={"file": ("t.xlsx", content, XLSX_MIME)})


def test_download_template(scheduler_env):
    client, _ = scheduler_env
    for entity in ("subjects", "teachers", "classes"):
        r = client.get(f"/api/import/templates/{entity}")
        assert r.status_code == 200
        assert r.headers["content-type"] == XLSX_MIME
        assert len(r.content) > 0


def test_import_subjects_ok(scheduler_env):
    client, sid = scheduler_env
    rows = [["数学", "数学学科", "普通教室", 1], ["物理", "科学", "专用教室", 2]]
    r = upload(client, "subjects", sid, rows, ncols=4)
    assert r.status_code == 200
    assert r.json() == {"imported": 2, "errors": []}
    assert len(client.get(f"/api/subjects?semester_id={sid}").json()) == 2


def test_import_subjects_invalid_room_type_zero_write(scheduler_env):
    """验收②:错误报告行号,数据库零写入。"""
    client, sid = scheduler_env
    rows = [["数学", "", "普通教室", 1], ["体育", "", "操场外", 1]]  # 第 5 行教室/场地类型无效
    r = upload(client, "subjects", sid, rows, ncols=4)
    body = r.json()
    assert body["imported"] == 0
    assert any("第 5 行" in e and "教室/场地类型" in e for e in body["errors"])
    # 零写入:连合法的第 4 行也未写入
    assert client.get(f"/api/subjects?semester_id={sid}").json() == []


def test_import_teachers_with_accounts(scheduler_env):
    """验收①:导入教师、创建账号、任教科目关联。"""
    client, sid = scheduler_env
    client.post(f"/api/subjects?semester_id={sid}", json={"name": "数学"})
    client.post(f"/api/subjects?semester_id={sid}", json={"name": "物理"})
    rows = [
        ["王小明", "1234", "数学、物理", 20, "排课管理员", 4, "否", "wang001"],
        ["李小华", "5678", "数学", 18, "", "", "是", "lee001"],
    ]
    r = upload(client, "teachers", sid, rows, create_accounts=True)
    assert r.json()["imported"] == 2
    teachers = client.get(f"/api/teachers?semester_id={sid}").json()
    wang = next(t for t in teachers if t["name"] == "王小明")
    assert {s["name"] for s in wang["subjects"]} == {"数学", "物理"}
    # 账号已创建,可用默认密码登录(首登需改密)
    client.post("/api/auth/logout")
    login = client.post("/api/auth/login", json={"username": "wang001", "password": "changeme"})
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True


def test_import_teachers_duplicate_name_id4(scheduler_env):
    client, sid = scheduler_env
    rows = [["王小明", "1234", "", "", "", "", "", ""], ["王小明", "1234", "", "", "", "", "", ""]]
    r = upload(client, "teachers", sid, rows)
    body = r.json()
    assert body["imported"] == 0
    assert any("重复" in e for e in body["errors"])
    assert client.get(f"/api/teachers?semester_id={sid}").json() == []


def test_import_teachers_unknown_subject(scheduler_env):
    client, sid = scheduler_env
    rows = [["王小明", "", "不存在的科目", "", "", "", "", ""]]
    body = upload(client, "teachers", sid, rows).json()
    assert body["imported"] == 0
    assert any("科目" in e for e in body["errors"])


def test_import_classes_with_homeroom(scheduler_env):
    """验收③相关:班级导入,班主任以姓名对应。"""
    client, sid = scheduler_env
    client.post(f"/api/teachers?semester_id={sid}", json={"name": "陈老师"})
    rows = [["1", "甲", "中职", "机械专业", "陈老师", 35]]
    r = upload(client, "classes", sid, rows, ncols=6)
    assert r.json()["imported"] == 1
    cu = client.get(f"/api/class-units?semester_id={sid}").json()[0]
    assert cu["department"] == "机械专业"
    assert cu["homeroom_teacher"]["name"] == "陈老师"


def test_import_classes_unknown_homeroom(scheduler_env):
    client, sid = scheduler_env
    rows = [["1", "甲", "小学", "", "查无此人", ""]]
    body = upload(client, "classes", sid, rows, ncols=6).json()
    assert body["imported"] == 0
    assert any("班主任" in e for e in body["errors"])


def test_import_invalid_file_rejected(scheduler_env):
    client, sid = scheduler_env
    r = client.post(
        f"/api/import/subjects?semester_id={sid}",
        files={"file": ("bad.xlsx", b"not an excel file", XLSX_MIME)},
    )
    assert r.status_code == 400
