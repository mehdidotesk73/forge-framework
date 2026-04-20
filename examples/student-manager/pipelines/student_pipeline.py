"""
Pipeline Layer — student-manager
Ingests raw student and grade CSVs; produces normalized students, grades,
and courses datasets.

Pipeline developers see only dataset UUIDs and schemas.
They have zero knowledge of object types, endpoints, or UI.
"""
from forge.pipeline import pipeline, ForgeInput, ForgeOutput

# Dataset UUIDs are assigned by `forge dataset load` and pasted here.
# Running `forge dataset load data/students.csv --name students_raw` prints the UUID.
PIPELINE_ID     = "aaaaaaaa-0000-0000-0000-000000000001"
STUDENTS_RAW_ID = "a869ec83-62b1-4f5c-89ed-a72df7f98d5f"
GRADES_RAW_ID   = "9c751038-6bf0-489f-aff6-9aab30378fc5"

STUDENTS_OUT_ID = "de271075-b375-4b05-bd79-eb710df8b2c3"
GRADES_OUT_ID   = "df13b4b7-8704-4082-8822-895de3d4ec41"
COURSES_OUT_ID  = "5904497f-dbc0-4f21-a9e8-a9eec9a7c6c8"


@pipeline(
    pipeline_id=PIPELINE_ID,
    inputs={
        "students_raw": ForgeInput(STUDENTS_RAW_ID),
        "grades_raw": ForgeInput(GRADES_RAW_ID),
    },
    outputs={
        "students": ForgeOutput(STUDENTS_OUT_ID),
        "grades": ForgeOutput(GRADES_OUT_ID),
        "courses": ForgeOutput(COURSES_OUT_ID),
    },
)
def run(inputs, outputs):
    students_df = inputs.students_raw.df()
    grades_df = inputs.grades_raw.df()

    # Normalize students — grade_keys is a JSON list of grade IDs maintained by the control layer
    students = students_df[["id", "name", "email", "major", "enrolled_at", "status"]].copy()
    students["grade_keys"] = "[]"
    outputs.students.write(students)

    # Normalize grades
    grades = grades_df[["id", "student_id", "course", "semester", "grade", "credits"]].copy()
    outputs.grades.write(grades)

    # Derive courses from grades
    courses = (
        grades_df[["course"]]
        .drop_duplicates()
        .rename(columns={"course": "code"})
        .assign(name=lambda df: df["code"])
    )
    outputs.courses.write(courses)
