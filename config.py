import os
from os import environ

# Telegram Bot Token from @Botfather
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8095429243:AAGJjnNYZgcb6EAGduIXc7D4V0WvRqxJeVo")

# List of authorized user IDs (Admins)
AUTHORIZED_USERS = list(map(int, os.environ.get("AUTHORIZED_USERS", "1397269319,6906650389,1489652480,8030133926").split(",")))      #For Example 123456,123456

# MongoDB URL and DB name
DB_URL = os.environ.get("DB_URL", "mongodb+srv://wemedia360:Ex3pPKO0PNBWcI6k@channelbroadcastbot.pqhuvuc.mongodb.net/?retryWrites=true&w=majority&appName=Channelbroadcastbot")
DB_NAME = os.environ.get("DB_NAME", "Channelbroadcastbot")

# Optional: List of default Telegram channels)
# You can add unlimited channel directy from bot)
DEFAULT_CHANNELS = list(map(int, os.environ.get("DEFAULT_CHANNELS", "-1002708988775,-1002524893260,-1002293619404,-1002447252037,-1002617751817,-1002599212023,-1002783719315").split(",")))      #-1001234567890,-1009876543210  For Example

DELETE_TIME = int(environ.get("DELETE_TIME", "30"))  #  deletion time in seconds (default: 5 minutes). Adjust as per your needs.
