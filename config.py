import enum
from os import getenv
from dotenv import load_dotenv

load_dotenv()

client_id = getenv('CLIENT_ID')
client_secret = getenv('CLIENT_SECRET')


class Setting(enum.Enum):
    AutoProcessRecordings = 'auto_process_recordings'
