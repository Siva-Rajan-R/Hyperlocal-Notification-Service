import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from typing import Dict, List, Optional
from datetime import datetime
from bson import ObjectId
from schemas.v1.notification_schemas import NotificationCreateSchema
from infras.db.mongo import get_collection

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])

# Connection Manager for WebSockets
class ConnectionManager:
    def __init__(self):
        # Maps user_id -> Active WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: str) -> bool:
        """Sends message if user is online, returns True/False success"""
        websocket = self.active_connections.get(user_id)
        if websocket:
            try:
                await websocket.send_json(message)
                return True
            except Exception:
                self.disconnect(user_id)
        return False

    async def broadcast(self, message: dict):
        """Broadcasts message to all currently connected users"""
        disconnected_users = []
        for user_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected_users.append(user_id)
        for user_id in disconnected_users:
            self.disconnect(user_id)

manager = ConnectionManager()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    
    # Upon connection, fetch stored offline notifications for this user
    try:
        collection = get_collection()
        cursor = collection.find({"user_id": user_id}).sort("created_at", 1)
        offline_notifications = await cursor.to_list(length=100)
        
        if offline_notifications:
            for notif in offline_notifications:
                # Convert ObjectId to str
                notif["id"] = str(notif.pop("_id"))
                if "created_at" in notif:
                    notif["created_at"] = notif["created_at"].isoformat()
                
                # Send to client
                await websocket.send_json(notif)
            
            # Delete/Clear delivered offline notifications
            await collection.delete_many({"user_id": user_id})
            
        # Keep connection open and listen
        while True:
            data = await websocket.receive_text()
            # We can handle heartbeat/ping-pong if needed
    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception:
        manager.disconnect(user_id)

# Push Notification API (Triggered by Retailer / Services)
@router.post("/send")
async def send_notification(data: NotificationCreateSchema):
    collection = get_collection()
    notif_data = {
        "title": data.title,
        "message": data.message,
        "type": data.type,
        "target_type": data.target_type,
        "created_at": datetime.utcnow(),
        "additional_metadata": data.additional_metadata
    }

    # Case A: Broadcast to ALL connected users
    if data.target_type == "all":
        # Send immediately to all connected
        await manager.broadcast({
            **notif_data,
            "created_at": notif_data["created_at"].isoformat()
        })
        # Note: Broadcasts to 'all' do not get stored for offline users
        return {"status": "broadcasted"}

    # Case B: Particular User IDs (or single user_id)
    target_users = data.user_ids or []
    if data.user_id and data.user_id not in target_users:
        target_users.append(data.user_id)

    if not target_users:
        raise HTTPException(status_code=400, detail="Must specify user_id or user_ids for particular notifications.")

    sent_count = 0
    stored_count = 0

    for user_id in target_users:
        user_notif = {**notif_data, "user_id": user_id}
        
        # Try sending to websocket
        was_sent = await manager.send_personal_message(
            {**user_notif, "created_at": user_notif["created_at"].isoformat()}, 
            user_id
        )
        
        if not was_sent:
            # Store offline notification in MongoDB
            await collection.insert_one(user_notif)
            stored_count += 1
        else:
            sent_count += 1

    return {"status": "processed", "sent_online": sent_count, "stored_offline": stored_count}

# GET Stored Notifications for a user (fallback)
@router.get("/")
async def get_notifications(user_id: str = Query(..., description="User ID to fetch stored notifications for")):
    collection = get_collection()
    cursor = collection.find({"user_id": user_id}).sort("created_at", -1)
    notifications = await cursor.to_list(length=100)
    
    result = []
    for notif in notifications:
        notif["id"] = str(notif.pop("_id"))
        result.append(notif)
        
    if result:
        await collection.delete_many({"user_id": user_id})
        
    return result

# DELETE a specific notification
@router.delete("/{notification_id}")
async def delete_notification(notification_id: str):
    collection = get_collection()
    try:
        res = await collection.delete_one({"_id": ObjectId(notification_id)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
        return {"status": "deleted"}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid notification ID format")
