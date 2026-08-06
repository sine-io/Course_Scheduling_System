"""学校名称设置测试。

学校名称支持在管理界面修改，并持久化到数据库。
"""

from app.core.config import settings as env_settings
from app.models.user import Role
from app.services import settings as app_settings
from tests.conftest import make_user

PW = "password123"


def _admin(client, db):
    make_user(db, "adm", PW, roles=[Role.admin])
    client.post("/api/auth/login", json={"username": "adm", "password": PW})
    return client


def test_falls_back_to_env_when_unset(env):
    """升级后仍兼容旧部署：未设置数据库值时沿用 .env。"""
    client, db = env
    assert app_settings.school_name(db) == env_settings.school_name
    assert _admin(client, db).get("/api/settings/school").json()["school_name"] == (
        env_settings.school_name
    )


def test_can_be_changed_without_restart(env):
    client, db = env
    _admin(client, db)
    r = client.put("/api/settings/school", json={"school_name": "海州市启明实验初级中学"})
    assert r.status_code == 200
    assert r.json()["school_name"] == "海州市启明实验初级中学"
    assert app_settings.school_name(db) == "海州市启明实验初级中学"


def test_blank_name_is_rejected(env):
    """空名称会使导出课表标题为空，因此在接口层拒绝。"""
    client, db = env
    _admin(client, db)
    assert client.put("/api/settings/school", json={"school_name": ""}).status_code == 422
    assert client.put("/api/settings/school", json={"school_name": "   "}).status_code == 200
    # 全空白会被 strip 成空字符串，读取时回退到 .env
    assert app_settings.school_name(db) == env_settings.school_name


def test_non_admin_cannot_change_it(env):
    client, db = env
    make_user(db, "s", PW, roles=[Role.scheduler])
    client.post("/api/auth/login", json={"username": "s", "password": PW})
    assert client.put("/api/settings/school", json={"school_name": "X"}).status_code == 403


def test_demo_data_sets_the_school_name(env):
    """加载示例数据时同步设置学校名称。"""
    client, db = env
    _admin(client, db)
    client.post("/api/demo-data")
    assert app_settings.school_name(db) == "海州市启明实验初级中学"
