from dotenv import load_dotenv
import os

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
GUILD_ID = int(os.getenv("GUILD_ID"))
CALENDER_ID=os.getenv("CALENDER_ID")
