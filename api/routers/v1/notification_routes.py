import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from typing import Dict, List, Optional
from datetime import datetime
from bson import ObjectId
from schemas.v1.notification_schemas import NotificationCreateSchema, MarkAllReadSchema
from infras.db.mongo import get_collection
from icecream import ic

router = APIRouter(prefix="/notifications", tags=["Notifications"])

def sanitize_for_json(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items() if k != "_id"}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    return obj

# Multi-connection Connection Manager for WebSockets
class ConnectionManager:
    def __init__(self):
        # Maps conn_key -> List of active WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, conn_keys: List[str], websocket: WebSocket):
        await websocket.accept()
        for key in conn_keys:
            if not key:
                continue
            if key not in self.active_connections:
                self.active_connections[key] = []
            if websocket not in self.active_connections[key]:
                self.active_connections[key].append(websocket)
        ic(f"[WS Connect] Registered connection for keys: {conn_keys}")

    def disconnect(self, websocket: WebSocket):
        keys_to_delete = []
        for key, sockets in self.active_connections.items():
            if websocket in sockets:
                sockets.remove(websocket)
            if not sockets:
                keys_to_delete.append(key)
        for key in keys_to_delete:
            del self.active_connections[key]
        ic(f"[WS Disconnect] Socket removed from active connections")

    async def send_personal_message(self, message: dict, targets: List[str]) -> bool:
        """Sends message to all active tabs/connections matching any of the targets. Avoids duplicate delivery to same socket."""
        delivered_sockets = set()
        delivered = False
        safe_message = sanitize_for_json(message)
        
        all_keys = []
        for t in targets:
            if t:
                all_keys.extend([t, f"particular:{t}"])

        for key in all_keys:
            websockets = self.active_connections.get(key, [])
            dead_sockets = []
            for ws in list(websockets):
                if ws in delivered_sockets:
                    continue
                try:
                    await ws.send_json(safe_message)
                    delivered_sockets.add(ws)
                    delivered = True
                except Exception as e:
                    ic(f"[WS Send Error] Failed to send to {key}: {e}")
                    dead_sockets.append(ws)
            for dead_ws in dead_sockets:
                self.disconnect(dead_ws)

        return delivered

    async def broadcast(self, message: dict):
        """Broadcasts message to all currently connected clients across all users."""
        delivered_sockets = set()
        safe_message = sanitize_for_json(message)
        for conn_key, websockets in list(self.active_connections.items()):
            dead_sockets = []
            for ws in list(websockets):
                if ws in delivered_sockets:
                    continue
                try:
                    await ws.send_json(safe_message)
                    delivered_sockets.add(ws)
                except Exception:
                    dead_sockets.append(ws)
            for dead_ws in dead_sockets:
                self.disconnect(dead_ws)

manager = ConnectionManager()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    shop_id: Optional[str] = Query(None)
):
    effective_shop_id = shop_id or websocket.query_params.get("shop_id")
    keys = [user_id]
    if effective_shop_id and effective_shop_id != user_id:
        keys.append(effective_shop_id)
    await manager.connect(keys, websocket)
    try:
        # Keep connection open, handle heartbeats / client messages
        while True:
            data = await websocket.receive_text()
            if data == "ping" or "ping" in data:
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        ic(f"[WS Endpoint Exception] {e}")
        manager.disconnect(websocket)

@router.websocket("/ws/{target_type}/{user_id}")
async def websocket_endpoint_typed(
    websocket: WebSocket,
    user_id: str,
    target_type: str,
    shop_id: Optional[str] = Query(None)
):
    effective_shop_id = shop_id or websocket.query_params.get("shop_id")
    keys = [user_id, f"{target_type}:{user_id}"]
    if effective_shop_id and effective_shop_id != user_id:
        keys.extend([effective_shop_id, f"{target_type}:{effective_shop_id}"])
    await manager.connect(keys, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping" or "ping" in data:
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        ic(f"[WS Endpoint Exception] {e}")
        manager.disconnect(websocket)


# Push Notification API (Triggered by Retailer / Services / RabbitMQ)
@router.post("/send")
async def send_notification(data: NotificationCreateSchema):
    collection = get_collection()
    now = datetime.utcnow()
    
    base_notif_data = {
        "title": data.title,
        "message": data.message,
        "type": data.type or "info",
        "target_type": data.target_type,
        "is_read": False,
        "read_at": None,
        "created_at": now,
        "additional_metadata": data.additional_metadata or {}
    }

    # Case A: Broadcast to ALL connected users
    if data.target_type == "all":
        # Always store the broadcast notification in MongoDB
        broadcast_doc = {**base_notif_data, "user_id": None}
        insert_res = await collection.insert_one(broadcast_doc)
        notif_id = str(insert_res.inserted_id)

        # Broadcast live over WebSocket (ensure strictly clean JSON types)
        ws_payload = {
            "id": notif_id,
            "title": data.title,
            "message": data.message,
            "type": data.type or "info",
            "target_type": "all",
            "user_id": None,
            "is_read": False,
            "read_at": None,
            "created_at": now.isoformat(),
            "additional_metadata": data.additional_metadata or {}
        }
        await manager.broadcast(ws_payload)
        return {"status": "broadcasted", "id": notif_id}

    # Case B: Particular User IDs (or single user_id / shop_id)
    target_users = list(data.user_ids or [])
    if data.user_id and data.user_id not in target_users:
        target_users.append(data.user_id)

    meta_shop_id = None
    if data.additional_metadata and isinstance(data.additional_metadata, dict):
        meta_shop_id = data.additional_metadata.get("shop_id")

    if not target_users and meta_shop_id:
        target_users.append(meta_shop_id)

    if not target_users:
        raise HTTPException(status_code=400, detail="Must specify user_id or user_ids for particular notifications.")

    sent_count = 0
    stored_count = 0
    created_ids = []

    # Gather all potential target keys for websocket delivery (user_id, shop_id, user_ids)
    all_push_targets = list(target_users)
    if meta_shop_id and meta_shop_id not in all_push_targets:
        all_push_targets.append(meta_shop_id)

    for user_id in target_users:
        user_notif = {**base_notif_data, "user_id": user_id}
        
        # Always store notification in MongoDB
        insert_res = await collection.insert_one(user_notif)
        notif_id = str(insert_res.inserted_id)
        created_ids.append(notif_id)
        stored_count += 1
        
        # Live push to active WebSocket connection(s) (ensure strictly clean JSON types)
        ws_payload = {
            "id": notif_id,
            "title": data.title,
            "message": data.message,
            "type": data.type or "info",
            "target_type": data.target_type or "particular",
            "user_id": user_id,
            "is_read": False,
            "read_at": None,
            "created_at": now.isoformat(),
            "additional_metadata": data.additional_metadata or {}
        }
        
        was_sent = await manager.send_personal_message(ws_payload, all_push_targets)
        if was_sent:
            sent_count += 1

    return {
        "status": "processed",
        "ids": created_ids,
        "sent_online": sent_count,
        "stored_db": stored_count
    }

# GET Notifications for a user (Persistent, Non-destructive)
@router.get("/")
async def get_notifications(
    user_id: str = Query(..., description="User ID to fetch notifications for"),
    shop_id: Optional[str] = Query(None, description="Shop ID"),
    unread_only: bool = Query(False, description="Filter only unread notifications"),
    limit: int = Query(100, description="Max notifications to fetch")
):
    collection = get_collection()
    or_conditions = [
        {"user_id": user_id},
        {"target_type": "all"}
    ]
    if shop_id and shop_id != user_id:
        or_conditions.append({"user_id": shop_id})
        or_conditions.append({"additional_metadata.shop_id": shop_id})

    query: dict = {"$or": or_conditions}
    if unread_only:
        query["is_read"] = False

    cursor = collection.find(query).sort("created_at", -1).limit(limit)
    notifications = await cursor.to_list(length=limit)
    
    result = []
    seen_ids = set()
    for notif in notifications:
        notif_id_str = str(notif.pop("_id"))
        if notif_id_str in seen_ids:
            continue
        seen_ids.add(notif_id_str)
        notif["id"] = notif_id_str
        if "created_at" in notif and isinstance(notif["created_at"], datetime):
            notif["created_at"] = notif["created_at"].isoformat()
        if "read_at" in notif and isinstance(notif["read_at"], datetime):
            notif["read_at"] = notif["read_at"].isoformat()
        # Default missing boolean
        if "is_read" not in notif:
            notif["is_read"] = False
        result.append(notif)
        
    return result


# PATCH Mark a single notification as read
@router.patch("/{notification_id}/read")
async def mark_as_read(notification_id: str):
    collection = get_collection()
    try:
        res = await collection.update_one(
            {"_id": ObjectId(notification_id)},
            {"$set": {"is_read": True, "read_at": datetime.utcnow()}}
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
        return {"status": "success", "id": notification_id, "is_read": True}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid notification ID format")

# PATCH Mark all notifications as read for a user / shop
@router.patch("/read-all")
async def mark_all_as_read(
    user_id: Optional[str] = Query(None),
    shop_id: Optional[str] = Query(None),
    payload: Optional[MarkAllReadSchema] = Body(None)
):
    target_user_id = user_id or (payload.user_id if payload else None)
    target_shop_id = shop_id or (payload.shop_id if payload else None)
    
    if not target_user_id and not target_shop_id:
        raise HTTPException(status_code=400, detail="User ID or Shop ID is required")
    
    or_conditions = [
        {"target_type": "all"}
    ]
    if target_user_id:
        or_conditions.append({"user_id": target_user_id})
    if target_shop_id:
        or_conditions.append({"user_id": target_shop_id})
        or_conditions.append({"additional_metadata.shop_id": target_shop_id})
    
    collection = get_collection()
    now = datetime.utcnow()
    res = await collection.update_many(
        {
            "$or": or_conditions,
            "is_read": {"$ne": True}
        },
        {"$set": {"is_read": True, "read_at": now}}
    )
    return {"status": "success", "modified_count": res.modified_count}

# DELETE all notifications for a user / shop
@router.delete("/clear-all")
async def clear_all_notifications(
    user_id: Optional[str] = Query(None, description="User ID"),
    shop_id: Optional[str] = Query(None, description="Shop ID")
):
    if not user_id and not shop_id:
        raise HTTPException(status_code=400, detail="User ID or Shop ID is required")
        
    or_conditions = []
    if user_id:
        or_conditions.append({"user_id": user_id})
    if shop_id:
        or_conditions.append({"user_id": shop_id})
        or_conditions.append({"additional_metadata.shop_id": shop_id})
        
    collection = get_collection()
    res = await collection.delete_many({"$or": or_conditions})
    return {"status": "success", "deleted_count": res.deleted_count}

# DELETE a specific notification
@router.delete("/{notification_id}")
async def delete_notification(notification_id: str):
    collection = get_collection()
    try:
        res = await collection.delete_one({"_id": ObjectId(notification_id)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
        return {"status": "deleted", "id": notification_id}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid notification ID format")

