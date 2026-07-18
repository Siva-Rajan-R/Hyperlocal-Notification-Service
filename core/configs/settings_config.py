import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PORT: int = 8009
    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "NotificationServiceDb"
    ENVIRONMENT: str = "development"
    RABBITMQ_HOST:str
    RABBITMQ_PORT:int
    RABBITMQ_LOGIN:str
    RABBITMQ_PASSWORD:str

    class Config:
        env_file = ".env"
        extra = "ignore"

SETTINGS = Settings()
