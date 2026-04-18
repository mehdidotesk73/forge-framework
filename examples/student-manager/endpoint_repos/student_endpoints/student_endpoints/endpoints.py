"""
Control Layer — student_endpoints repo

Imports model types from the model layer and exposes operations as endpoints.
The Forge engine is provided by the framework via context — endpoint functions
never declare or receive it explicitly.
"""

from __future__ import annotations

import json
import uuid
from datetime import date

from forge.control import action_endpoint, computed_column_endpoint
from models.student import Student
from models.grade import Grade

CREATE_STUDENT_ID = "11111111-0000-0000-0000-000000000001"
COMPUTE_METRICS_ID = "11111111-0000-0000-0000-000000000002"
CREATE_GRADE_ID = "11111111-0000-0000-0000-000000000003"
EDIT_STUDENT_ID = "11111111-0000-0000-0000-000000000004"
DELETE_STUDENT_ID = "11111111-0000-0000-0000-000000000005"
EDIT_GRADE_ID = "11111111-0000-0000-0000-000000000006"
DELETE_GRADE_ID = "11111111-0000-0000-0000-000000000007"

_GRADE_POINTS: dict[str, float] = {
    "A": 4.0,
    "A-": 3.7,
    "B+": 3.3,
    "B": 3.0,
    "B-": 2.7,
    "C+": 2.3,
    "C": 2.0,
    "C-": 1.7,
    "D+": 1.3,
    "D": 1.0,
    "F": 0.0,
}


@action_endpoint(
    name="create_student",
    endpoint_id=CREATE_STUDENT_ID,
    description="Create a new student record",
    params=[
        {"name": "name", "type": "string", "required": True},
        {"name": "email", "type": "string", "required": True},
        {"name": "major", "type": "string", "required": True},
        {"name": "enrolled_at", "type": "string", "required": False, "default": ""},
        {"name": "status", "type": "string", "required": False, "default": "active"},
    ],
)
def create_student(
    name: str, email: str, major: str, enrolled_at: str = "", status: str = "active"
) -> dict:
    student = Student.create(
        id=f"s{uuid.uuid4().hex[:6]}",
        name=name,
        email=email,
        major=major,
        enrolled_at=enrolled_at or str(date.today()),
        status=status,
        grade_keys="[]",
    )
    return student._to_dict()


@action_endpoint(
    name="edit_student",
    endpoint_id=EDIT_STUDENT_ID,
    description="Update an existing student record",
    params=[
        {"name": "id", "type": "string", "required": True},
        {"name": "name", "type": "string", "required": False, "default": ""},
        {"name": "email", "type": "string", "required": False, "default": ""},
        {"name": "major", "type": "string", "required": False, "default": ""},
        {"name": "enrolled_at", "type": "string", "required": False, "default": ""},
        {"name": "status", "type": "string", "required": False, "default": ""},
    ],
)
def edit_student(
    id: str,
    name: str = "",
    email: str = "",
    major: str = "",
    enrolled_at: str = "",
    status: str = "",
) -> dict:
    student = Student.get(id)
    if student is None:
        return {"error": f"Student {id} not found"}

    updates = {k: v for k, v in {"name": name, "email": email, "major": major, "enrolled_at": enrolled_at, "status": status}.items() if v != ""}
    student.update(**updates)
    return student._to_dict()


@action_endpoint(
    name="delete_student",
    endpoint_id=DELETE_STUDENT_ID,
    description="Delete a student record",
    params=[{"name": "id", "type": "string", "required": True}],
)
def delete_student(id: str) -> dict:
    student = Student.get(id)
    if student is None:
        return {"error": f"Student {id} not found"}
    student.remove()
    return {"deleted": id}


@action_endpoint(
    name="create_grade",
    endpoint_id=CREATE_GRADE_ID,
    description="Record a grade for a student",
    params=[
        {"name": "student_id", "type": "string", "required": True},
        {"name": "course", "type": "string", "required": True},
        {"name": "semester", "type": "string", "required": True},
        {"name": "grade", "type": "string", "required": True},
        {"name": "credits", "type": "integer", "required": False, "default": 3},
    ],
)
def create_grade(
    student_id: str, course: str, semester: str, grade: str, credits: int = 3
) -> dict:
    new_grade = Grade.create(
        id=f"g{uuid.uuid4().hex[:6]}",
        student_id=student_id,
        course=course,
        semester=semester,
        grade=grade,
        credits=int(credits),
    )

    student = Student.get(student_id)
    if student is not None:
        keys = json.loads(student.grade_keys or "[]")
        keys.append(new_grade.id)
        student.grade_keys = json.dumps(keys)  # dirty-tracked → flushed atomically

    return new_grade._to_dict()


@computed_column_endpoint(
    object_type="Student",
    columns=["gpa", "rank"],
    endpoint_id=COMPUTE_METRICS_ID,
    name="compute_student_metrics",
    description="Compute GPA and rank per student from linked grade records",
    params=[
        {
            "name": "timeframe",
            "type": "string",
            "required": False,
            "description": "Semester (e.g. '2023-fall') or 'all'",
            "default": "all",
        },
    ],
)
def compute_student_metrics(students: list[Student], timeframe: str = "all") -> dict:
    gpas: list[float | None] = []
    for student in students:
        grades = student.grades()  # follows grade_keys; engine read from context

        if timeframe and timeframe != "all":
            grades = [g for g in grades if g.semester == timeframe]

        if not grades:
            gpas.append(None)
            continue

        total_points = sum(
            _GRADE_POINTS.get(g.grade or "", 0.0) * (g.credits or 0) for g in grades
        )
        total_credits = sum(g.credits or 0 for g in grades)
        gpas.append(round(total_points / total_credits, 2) if total_credits else 0.0)

    sorted_idx = sorted(
        range(len(gpas)),
        key=lambda i: (gpas[i] is not None, gpas[i] if gpas[i] is not None else -1.0),
        reverse=True,
    )
    ranks = [0] * len(gpas)
    for pos, idx in enumerate(sorted_idx, 1):
        ranks[idx] = pos

    return {
        s.id: {"gpa": gpa, "rank": rank} for s, gpa, rank in zip(students, gpas, ranks)
    }


@action_endpoint(
    name="edit_grade",
    endpoint_id=EDIT_GRADE_ID,
    description="Update the grade letter and credit count for an existing grade record",
    params=[
        {"name": "id", "type": "string", "required": True},
        {"name": "course", "type": "string", "required": False, "default": ""},
        {"name": "semester", "type": "string", "required": False, "default": ""},
        {"name": "grade", "type": "string", "required": False, "default": ""},
        {"name": "credits", "type": "integer", "required": False, "default": 0},
    ],
)
def edit_grade(
    id: str, course: str = "", semester: str = "", grade: str = "", credits: int = 0
) -> dict:
    g = Grade.get(id)
    if g is None:
        return {"error": f"Grade {id} not found"}
    g.update(course=course, semester=semester, grade=grade, credits=int(credits))
    return g._to_dict()


@action_endpoint(
    name="delete_grade",
    endpoint_id=DELETE_GRADE_ID,
    description="Delete a grade record and remove it from the student",
    params=[
        {"name": "id", "type": "string", "required": True},
        {"name": "student_id", "type": "string", "required": True},
    ],
)
def delete_grade(id: str, student_id: str) -> dict:
    g = Grade.get(id)
    if g is None:
        return {"error": f"Grade {id} not found"}
    g.remove()
    student = Student.get(student_id)
    if student is not None:
        keys = json.loads(student.grade_keys or "[]")
        if id in keys:
            keys.remove(id)
            student.grade_keys = json.dumps(keys)
    return {"deleted": id}
