from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
import uuid

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
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class DocumentStatus(BaseModel):
    id: str
    status: str
    error_message: Optional[str] = None
