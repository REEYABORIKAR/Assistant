from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentBase(BaseModel):
    file_name: str
    file_type: str
    file_size: int
    project_id: str
    workspace_id: str

class DocumentCreate(DocumentBase):
    pass

class DocumentResponse(DocumentBase):
    id: str
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DocumentStatus(BaseModel):
    id: str
    status: str
    error_message: str | None = None
