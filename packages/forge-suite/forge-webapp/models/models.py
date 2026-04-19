from forge.model import forge_model, field_def, ForgeSnapshotModel

FORGE_PROJECT_DATASET_ID  = "09c6533b-b8b5-43f4-b500-acc05d191fe1"
ARTIFACT_STAMP_DATASET_ID = "cce19a08-9bef-4781-b6b1-de1c4eec13c6"
PIPELINE_DATASET_ID       = "4f9fef2c-ef90-4ae8-a887-94989caa2af3"
PIPELINE_RUN_DATASET_ID   = "3a7b282a-80a5-403b-b599-24dea2350502"
OBJECT_TYPE_DATASET_ID    = "5d31be44-da94-4eb4-9f55-31b285e081db"
ENDPOINT_REPO_DATASET_ID  = "74cfd862-1241-43fc-b01e-390cae2ee457"
ENDPOINT_DATASET_ID       = "2da6c8c1-03f6-49d2-9b7c-d9429cf347d8"
APP_DATASET_ID            = "83c25824-f5c8-478f-baaa-3ac3900a2c3a"


@forge_model(mode="snapshot", backing_dataset=FORGE_PROJECT_DATASET_ID)
class ForgeProject(ForgeSnapshotModel):
    id: str = field_def(primary_key=True, display="ID")
    name: str = field_def(display="Name")
    root_path: str = field_def(display="Root Path")
    forge_version: str = field_def(display="Forge Version")
    is_active: str = field_def(display="Active")  # "true" | "false"
    registered_at: str = field_def(display="Registered At", display_hint="datetime")


@forge_model(mode="snapshot", backing_dataset=ARTIFACT_STAMP_DATASET_ID)
class ArtifactStamp(ForgeSnapshotModel):
    id: str = field_def(primary_key=True, display="ID")
    project_id: str = field_def(display="Project ID")
    artifact_type: str = field_def(display="Type")   # model | endpoint | pipeline
    artifact_name: str = field_def(display="Name")
    built_at: str = field_def(display="Built At", display_hint="datetime")
    status: str = field_def(display="Status")         # ok | error


@forge_model(mode="snapshot", backing_dataset=PIPELINE_DATASET_ID)
class Pipeline(ForgeSnapshotModel):
    id: str = field_def(primary_key=True, display="ID")
    project_id: str = field_def(display="Project ID")
    name: str = field_def(display="Name")
    module: str = field_def(display="Module")
    function_name: str = field_def(display="Function")
    schedule: str = field_def(display="Schedule")
    input_datasets: str = field_def(display="Inputs")   # JSON list of dataset IDs
    output_datasets: str = field_def(display="Outputs")  # JSON list of dataset IDs


@forge_model(mode="snapshot", backing_dataset=PIPELINE_RUN_DATASET_ID)
class PipelineRun(ForgeSnapshotModel):
    id: str = field_def(primary_key=True, display="ID")
    project_id: str = field_def(display="Project ID")
    pipeline_name: str = field_def(display="Pipeline")
    started_at: str = field_def(display="Started At", display_hint="datetime")
    finished_at: str = field_def(display="Finished At", display_hint="datetime")
    status: str = field_def(display="Status")    # running | ok | error
    row_count: str = field_def(display="Rows")
    error_msg: str = field_def(display="Error")


@forge_model(mode="snapshot", backing_dataset=OBJECT_TYPE_DATASET_ID)
class ObjectType(ForgeSnapshotModel):
    id: str = field_def(primary_key=True, display="ID")
    project_id: str = field_def(display="Project ID")
    name: str = field_def(display="Name")
    mode: str = field_def(display="Mode")             # snapshot | stream
    module: str = field_def(display="Module")
    backing_dataset_id: str = field_def(display="Dataset ID")
    field_count: str = field_def(display="Fields")
    built_at: str = field_def(display="Built At", display_hint="datetime")


@forge_model(mode="snapshot", backing_dataset=ENDPOINT_REPO_DATASET_ID)
class EndpointRepo(ForgeSnapshotModel):
    id: str = field_def(primary_key=True, display="ID")
    project_id: str = field_def(display="Project ID")
    name: str = field_def(display="Name")
    path: str = field_def(display="Path")
    endpoint_count: str = field_def(display="Endpoints")


@forge_model(mode="snapshot", backing_dataset=ENDPOINT_DATASET_ID)
class Endpoint(ForgeSnapshotModel):
    id: str = field_def(primary_key=True, display="ID")
    project_id: str = field_def(display="Project ID")
    repo_name: str = field_def(display="Repo")
    endpoint_id: str = field_def(display="Endpoint ID")
    name: str = field_def(display="Name")
    kind: str = field_def(display="Kind")        # action | computed_attribute | streaming
    description: str = field_def(display="Description")
    object_type: str = field_def(display="Object Type")


@forge_model(mode="snapshot", backing_dataset=APP_DATASET_ID)
class App(ForgeSnapshotModel):
    id: str = field_def(primary_key=True, display="ID")
    project_id: str = field_def(display="Project ID")
    name: str = field_def(display="Name")
    app_id: str = field_def(display="App ID")
    path: str = field_def(display="Path")
    port: str = field_def(display="Port")


PROJECT_FILE_DATASET_ID = "e1d9f484-1fd9-47e6-9e5a-db6de289f9d6"


@forge_model(mode="snapshot", backing_dataset=PROJECT_FILE_DATASET_ID)
class ProjectFile(ForgeSnapshotModel):
    id: str = field_def(primary_key=True, display="ID")
    project_id: str = field_def(display="Project ID")
    filename: str = field_def(display="Filename")
    size_bytes: str = field_def(display="Size (bytes)")
    added_at: str = field_def(display="Added At", display_hint="datetime")
