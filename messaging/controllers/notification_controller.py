from aio_pika.abc import AbstractIncomingMessage
import orjson
from icecream import ic
from schemas.v1.notification_schemas import NotificationCreateSchema
from api.routers.v1.notification_routes import send_notification

async def notification_message_controller(msg: AbstractIncomingMessage):
    async with msg.process():
        try:
            payload = orjson.loads(msg.body)
            ic("Received notification via message queue:", payload)
            
            # Convert payload to Pydantic schema
            notif_schema = NotificationCreateSchema(**payload)
            
            # Send notification (this automatically handles ws broadcast / offline storage)
            res = await send_notification(notif_schema)
            ic("Notification processed via message queue:", res)
            
        except Exception as e:
            ic("Failed to process notification message queue event:", e)
