from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class NotificationCreateSchema(BaseModel):
    user_id: Optional[str] = None  # None/empty for broadcast (All)
    title: str
    message: str
    type: str = "info"  # info, error, warning, announcement
    target_type: str = "particular" # all, particular
    user_ids: Optional[List[str]] = None # list of specific users for announcement
    additional_metadata: Optional[dict] = Field(default_factory=dict)

class NotificationResponseSchema(BaseModel):
    id: str
    user_id: Optional[str]
    title: str
    message: str
    type: str
    target_type: str
    created_at: datetime
    additional_metadata: dict
