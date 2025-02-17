from datetime import datetime
from typing import Optional
import uuid
from pydantic import BaseModel, Field, EmailStr

class PDFRecord(BaseModel):
    """Schema for a record stored in DynamoDB."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="id")
    name: str
    email: EmailStr = "unknown@example.com"
    sex: str = "Unknown"
    content: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    deleted_at: Optional[str] = None