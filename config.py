import os
from os import environ

# Telegram Bot Token from @Botfather
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8356551419:AAGFZnpBbEaYeUh-t2CP-XGU3gMazpHX_pw")

# List of authorized user IDs (Admins)
AUTHORIZED_USERS = list(map(int, os.environ.get("AUTHORIZED_USERS", "1397269319,6906650389").split(",")))      #For Example 123456,123456

# MongoDB URL and DB name
DB_URL = os.environ.get("DB_URL", "mongodb+srv://wemedia360:Ex3pPKO0PNBWcI6k@channelbroadcastbot.pqhuvuc.mongodb.net/?retryWrites=true&w=majority&appName=Channelbroadcastbot")
DB_NAME = os.environ.get("DB_NAME", "Channelbroadcastbot")

# Optional: List of default Telegram channels)
# You can add unlimited channel directy from bot)
DEFAULT_CHANNELS = list(map(int, os.environ.get("DEFAULT_CHANNELS", "-1002805570628,-1001842318978").split(",")))      #-1001234567890,-1009876543210  For Example

DELETE_TIME = int(environ.get("DELETE_TIME", "300"))  #  deletion time in seconds (default: 5 minutes). Adjust as per your needs.
