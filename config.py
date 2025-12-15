import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    REDIS_URL = os.getenv('REDIS_URL')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    ADMIN_ID = 1232694251
    MAX_PLAYERS = int(os.getenv('MAX_PLAYERS', 71))

    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required in .env file")
        return True
