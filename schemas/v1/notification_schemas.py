from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class NotificationCreateSchema(BaseModel):
    user_id: Optional[str] = None  # None/empty for broadcast (All)
    title: str
    message: str
    type: str = "info"  # info, error, warning, success, announcement
    target_type: str = "particular" # all, particular
    user_ids: Optional[List[str]] = None # list of specific users for announcement
    additional_metadata: Optional[dict] = Field(default_factory=dict)

class NotificationResponseSchema(BaseModel):
    id: str
    user_id: Optional[str] = None
    title: str
    message: str
    type: str = "info"
    target_type: str = "particular"
    is_read: bool = False
    read_at: Optional[datetime] = None
    created_at: datetime
    additional_metadata: Optional[dict] = Field(default_factory=dict)

class MarkAllReadSchema(BaseModel):
    user_id: Optional[str] = None
    shop_id: Optional[str] = None

