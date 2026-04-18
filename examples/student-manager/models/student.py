"""
Model Layer — Student (snapshot)
Declares the Student object type backed by the students pipeline output.
After `forge model build`, the snapshot dataset is severed from the pipeline
and all mutations go to the snapshot copy.
"""
from forge.model import forge_model, field_def, related, ForgeSnapshotModel

# UUID of the students output dataset produced by student_pipeline
STUDENTS_DATASET_ID = "de271075-b375-4b05-bd79-eb710df8b2c3"


@forge_model(mode="snapshot", backing_dataset=STUDENTS_DATASET_ID)
class Student(ForgeSnapshotModel):
    id: str = field_def(primary_key=True, display="ID")
    name: str = field_def(display="Name")
    email: str = field_def(display="Email")
    major: str = field_def(display="Major")
    enrolled_at: str = field_def(display="Enrolled", display_hint="date")
    status: str = field_def(display="Status")
    # JSON-encoded list of grade IDs e.g. '["g001","g002"]' — maintained by create_grade
    grade_keys: str = field_def(display="Grade Keys")

    grades = related("Grade", via="grade_keys")
