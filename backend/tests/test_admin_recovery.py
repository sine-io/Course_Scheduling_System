"""部署级内置管理员恢复:解除锁定、撤销 session 并留下审计。"""

from datetime import UTC, datetime, timedelta

from app.core.security import verify_password
from app.models.audit import AuditLog
from app.models.user import Role
from app.scripts.recover_admin import recover_builtin_admin
from tests.conftest import make_user

PW = "password123"
RECOVERED = "recovered-password-123"


def test_recover_builtin_admin_invalidates_sessions_and_forces_password_change(env):
    client, db = env
    admin = make_user(db, "admin", PW, roles=[Role.admin])
    login = client.post("/api/auth/login", json={"username": "admin", "password": PW})
    assert login.status_code == 200
    old_session = client.cookies.get("session")

    admin.failed_login_attempts = 4
    admin.locked_until = datetime.now(UTC) + timedelta(minutes=15)
    db.commit()

    recovered = recover_builtin_admin(db, RECOVERED)

    assert recovered.id == admin.id
    assert recovered.is_builtin is True
    assert recovered.is_active is True
    assert recovered.failed_login_attempts == 0
    assert recovered.locked_until is None
    assert recovered.must_change_password is True
    assert verify_password(RECOVERED, recovered.password_hash)
    assert client.cookies.get("session") == old_session
    assert client.get("/api/auth/me").status_code == 401

    audit = db.query(AuditLog).filter(AuditLog.action == "recover_builtin_admin").one()
    assert audit.user_id is None
    assert audit.username == "deployment-recovery"
    assert audit.target_id == admin.id
    assert audit.result == "success"
    assert RECOVERED not in audit.detail

    new_login = client.post(
        "/api/auth/login", json={"username": "admin", "password": RECOVERED}
    )
    assert new_login.status_code == 200
    assert new_login.json()["must_change_password"] is True
    assert client.get("/api/auth/me").status_code == 200
    protected = client.get("/api/_protected")
    assert protected.status_code == 403
    assert protected.headers["x-reason"] == "must_change_password"
