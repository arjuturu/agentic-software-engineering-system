from pydantic import BaseModel, ConfigDict, Field


class ArtifactRecordResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(alias="fileName")
    artifact_type: str = Field(alias="artifactType")
    version: int
    status: str


class ArtifactContentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(alias="fileName")
    content: str


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: str = Field(alias="eventType")
    stage: str | None
    actor_type: str = Field(alias="actorType")
    actor_id: str | None = Field(alias="actorId")
    details: dict | None
    occurred_at: str = Field(alias="occurredAt")
