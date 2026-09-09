"""Track which teaching-assignment inputs a timetable was built from."""

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment import (
    AssignmentTeacher,
    BlockRule,
    CourseAssignment,
    SchedulingUnit,
    SchedulingUnitMember,
)
from app.models.timetable import Timetable


def fingerprint(db: Session, semester_id: int) -> str:
    """Return a stable digest of assignment data that changes a schedule."""
    assignments = db.execute(
        select(
            CourseAssignment.id,
            CourseAssignment.task_code,
            CourseAssignment.component,
            CourseAssignment.scheduling_unit_id,
            CourseAssignment.subject_id,
            CourseAssignment.periods_per_week,
            CourseAssignment.required_room_type,
            CourseAssignment.room_id,
            CourseAssignment.lock_room,
        )
        .where(CourseAssignment.semester_id == semester_id)
        .order_by(CourseAssignment.id)
    ).all()
    assignment_teachers = db.execute(
        select(
            AssignmentTeacher.course_assignment_id,
            AssignmentTeacher.teacher_id,
            AssignmentTeacher.is_lead,
        )
        .join(CourseAssignment)
        .where(CourseAssignment.semester_id == semester_id)
        .order_by(AssignmentTeacher.course_assignment_id, AssignmentTeacher.teacher_id)
    ).all()
    block_rules = db.execute(
        select(
            BlockRule.course_assignment_id,
            BlockRule.block_size,
            BlockRule.count_per_week,
        )
        .join(CourseAssignment)
        .where(CourseAssignment.semester_id == semester_id)
        .order_by(
            BlockRule.course_assignment_id,
            BlockRule.block_size,
            BlockRule.count_per_week,
        )
    ).all()
    units = db.execute(
        select(SchedulingUnit.id, SchedulingUnit.unit_type)
        .where(SchedulingUnit.semester_id == semester_id)
        .order_by(SchedulingUnit.id)
    ).all()
    unit_members = db.execute(
        select(
            SchedulingUnitMember.scheduling_unit_id,
            SchedulingUnitMember.class_unit_id,
        )
        .join(SchedulingUnit)
        .where(SchedulingUnit.semester_id == semester_id)
        .order_by(
            SchedulingUnitMember.scheduling_unit_id,
            SchedulingUnitMember.class_unit_id,
        )
    ).all()
    payload = {
        "assignments": [list(row) for row in assignments],
        "assignment_teachers": [list(row) for row in assignment_teachers],
        "block_rules": [list(row) for row in block_rules],
        "units": [list(row) for row in units],
        "unit_members": [list(row) for row in unit_members],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def stamp(db: Session, timetable: Timetable) -> str:
    """Record the current assignment snapshot on a timetable artifact."""
    value = fingerprint(db, timetable.semester_id)
    timetable.assignment_input_fingerprint = value
    return value


def is_current(db: Session, timetable: Timetable | None) -> bool | None:
    """Compare an artifact with current inputs; None means a legacy artifact."""
    if timetable is None or timetable.assignment_input_fingerprint is None:
        return None
    return timetable.assignment_input_fingerprint == fingerprint(db, timetable.semester_id)
