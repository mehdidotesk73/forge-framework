"""
Model Layer — Grade (stream)
Grade is a stream object: it stays linked to the grades pipeline output.
When the pipeline reruns, the Grade object set reflects the new data.
Read-only; no CRUD operations.
"""
from forge.model import forge_model, field_def, ForgeSnapshotModel

GRADES_DATASET_ID = "df13b4b7-8704-4082-8822-895de3d4ec41"


@forge_model(mode="snapshot", backing_dataset=GRADES_DATASET_ID)
class Grade(ForgeSnapshotModel):
    id: str = field_def(primary_key=True, display="ID")
    student_id: str = field_def(display="Student ID")
    course: str = field_def(display="Course")
    semester: str = field_def(display="Semester")
    grade: str = field_def(display="Grade")
    credits: int = field_def(display="Credits")
