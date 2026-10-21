"""
Announcement endpoints for the High School Management System API
"""

from datetime import date
from typing import Dict, Any, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    start_date: Optional[date] = None
    expiration_date: date

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message must not be blank")
        return value

    @model_validator(mode="after")
    def check_dates(self):
        if self.start_date and self.start_date > self.expiration_date:
            raise ValueError("Start date must not be after expiration date")
        return self


def require_teacher(teacher_username: Optional[str]) -> None:
    if not teacher_username:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")
    if not teachers_collection.find_one({"_id": teacher_username}):
        raise HTTPException(
            status_code=401, detail="Invalid teacher credentials")


def serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc["_id"],
        "message": doc["message"],
        "start_date": doc.get("start_date"),
        "expiration_date": doc["expiration_date"]
    }


def to_document(payload: AnnouncementIn) -> Dict[str, Any]:
    return {
        "message": payload.message,
        "start_date": payload.start_date.isoformat() if payload.start_date else None,
        "expiration_date": payload.expiration_date.isoformat()
    }


@router.get("/active")
def get_active_announcements() -> List[Dict[str, Any]]:
    """Public: announcements that have started and not yet expired"""
    today = date.today().isoformat()
    query = {
        "expiration_date": {"$gte": today},
        "$or": [{"start_date": None}, {"start_date": {"$lte": today}}]
    }
    docs = announcements_collection.find(query).sort("expiration_date", 1)
    return [serialize(d) for d in docs]


@router.get("")
def list_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """List all announcements - requires authentication"""
    require_teacher(teacher_username)
    docs = announcements_collection.find().sort("expiration_date", 1)
    return [serialize(d) for d in docs]


@router.post("", status_code=201)
def create_announcement(payload: AnnouncementIn, teacher_username: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Create an announcement - requires authentication"""
    require_teacher(teacher_username)
    doc = {"_id": str(uuid4()), **to_document(payload)}
    announcements_collection.insert_one(doc)
    return serialize(doc)


@router.put("/{announcement_id}")
def update_announcement(announcement_id: str, payload: AnnouncementIn, teacher_username: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Update an announcement - requires authentication"""
    require_teacher(teacher_username)
    result = announcements_collection.update_one(
        {"_id": announcement_id}, {"$set": to_document(payload)})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return serialize(announcements_collection.find_one({"_id": announcement_id}))


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, teacher_username: Optional[str] = Query(None)) -> Dict[str, str]:
    """Delete an announcement - requires authentication"""
    require_teacher(teacher_username)
    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"message": "Announcement deleted"}
