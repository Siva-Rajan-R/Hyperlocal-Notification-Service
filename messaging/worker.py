from .main import RabbitMQMessagingConfig, ExchangeType
from .controllers.notification_controller import notification_message_controller
import asyncio
from icecream import ic

async def worker():
    try:
        ic("Initializing Notification Service RabbitMQ Worker...")
        rabbitmq_conn = await RabbitMQMessagingConfig.get_rabbitmq_connection()
        rabbitmq_msg_obj = RabbitMQMessagingConfig(rabbitMQ_connection=rabbitmq_conn)

        # Declare Exchange
        exchange_name = 'notifications.service.exchange'
        await rabbitmq_msg_obj.create_exchange(name=exchange_name, exchange_type=ExchangeType.DIRECT)

        # Declare Queue and Bind
        queue_name = 'notifications.service.queue'
        routing_key = 'notifications.service.routing.key'
        await rabbitmq_msg_obj.create_queue(
            exchange_name=exchange_name,
            queue_name=queue_name,
            routing_key=routing_key
        )

        # Start Consuming
        await rabbitmq_msg_obj.consume_event(queue_name=queue_name, handler=notification_message_controller)
        ic("Notification Service RabbitMQ Worker is now listening for events 👂")
        
    except Exception as e:
        ic("Failed to start Notification Service RabbitMQ Worker:", e)
