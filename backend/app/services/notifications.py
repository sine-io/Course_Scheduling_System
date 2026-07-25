"""通知服务(M4-1 起,M4-3 补齐发送渠道)。

**站内通知始终可用**：写入 `notifications` 记录即完成，通知铃会轮询读取。
**电子邮件为补充渠道**：数据提交后才进入发送队列，发送失败不影响教学任务。

发送逻辑以 `NotificationChannel` 分层（architecture.md §5.3）：MVP 包含站内通知和
电子邮件两个渠道；后续增加 webhook 时只需实现新渠道并加入 `CHANNELS`。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.models.basedata import Teacher
from app.models.notification import Notification, NotificationType

logger = logging.getLogger(__name__)

_OUTBOX_KEY = "notification_email_outbox"


@dataclass(frozen=True, slots=True)
class _Email:
    to: str
    subject: str
    body: str


# ── 发送渠道 ────────────────────────────────────────────────
class NotificationChannel(Protocol):
    key: str

    def deliver(self, db: Session, notification: Notification, teacher: Teacher | None) -> None:
        ...


class InAppChannel:
    """站内通知:`notifications` 那一列本身即送达,无额外动作。"""

    key = "in_app"

    def deliver(self, db: Session, notification: Notification, teacher: Teacher | None) -> None:
        return


class EmailChannel:
    """Email:把邮件放进事务发件箱;commit 后由 after_commit 事件排入 RQ。

    这里不直接 enqueue——事务若回滚,就不该发送对应于不存在通知的邮件。
    """

    key = "email"

    def deliver(self, db: Session, notification: Notification, teacher: Teacher | None) -> None:
        if teacher is None or not teacher.email:
            return
        outbox = db.info.setdefault(_OUTBOX_KEY, [])
        outbox.append(_Email(
            to=teacher.email,
            subject=f"[{notification_subject_prefix()}] {notification.title}",
            body=notification.body or notification.title,
        ))


CHANNELS: list[NotificationChannel] = [InAppChannel(), EmailChannel()]


def notification_subject_prefix() -> str:
    from app.core.config import settings

    return settings.school_name


# ── 写入 ────────────────────────────────────────────────────
def notify(
    db: Session,
    *,
    semester_id: int,
    teacher_id: int | None,
    type: NotificationType,
    title: str,
    body: str = "",
    link: str = "",
) -> Notification:
    """创建通知并通过各渠道发送。调用方负责提交事务；电子邮件在提交后自动发送。"""
    n = Notification(
        semester_id=semester_id, teacher_id=teacher_id, type=type.value,
        title=title[:120], body=body, link=link[:200],
    )
    db.add(n)
    teacher = db.get(Teacher, teacher_id) if teacher_id is not None else None
    for channel in CHANNELS:
        channel.deliver(db, n, teacher)
    return n


# ── commit 后把发件箱中的邮件排入 RQ ─────────────────────────
@event.listens_for(Session, "after_commit")
def _flush_email_outbox(session: Session) -> None:
    outbox: list[_Email] = session.info.pop(_OUTBOX_KEY, [])
    if not outbox:
        return
    try:
        from app.workers.queue import enqueue_email
    except Exception:  # noqa: BLE001 - 测试或无 Redis 环境:静默跳过 Email
        return
    for msg in outbox:
        try:
            enqueue_email(msg.to, msg.subject, msg.body)
        except Exception:  # noqa: BLE001 - 队列不可用不该让已提交的事务报错
            # 站内通知已送达;Email 只是加分。但要留痕,否则 Redis 挂掉时无声消失无从查起
            logger.warning("代课通知 Email 排入队列失败(收件:%s),站内通知不受影响", msg.to)


@event.listens_for(Session, "after_rollback")
def _discard_email_outbox(session: Session) -> None:
    session.info.pop(_OUTBOX_KEY, None)


# ── 读取与状态 ──────────────────────────────────────────────
@dataclass
class NotificationView:
    items: list[Notification] = field(default_factory=list)
    unread: int = 0


def for_teacher(db: Session, semester_id: int, teacher_id: int) -> list[Notification]:
    return list(
        db.scalars(
            select(Notification)
            .where(
                Notification.semester_id == semester_id,
                Notification.teacher_id == teacher_id,
            )
            .order_by(Notification.id.desc())
        )
    )


def unread_count(db: Session, semester_id: int, teacher_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.semester_id == semester_id,
            Notification.teacher_id == teacher_id,
            Notification.read_at.is_(None),
        )
    ) or 0


def mark_read(notification: Notification) -> None:
    if notification.read_at is None:
        notification.read_at = datetime.now().astimezone()


def acknowledge(notification: Notification) -> None:
    now = datetime.now().astimezone()
    if notification.read_at is None:
        notification.read_at = now
    notification.acknowledged_at = now
