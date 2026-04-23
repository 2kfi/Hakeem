import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ZIM_DATA_PATH = os.getenv("ZIM_DATA_PATH", "/data/zimfiles")
SERVER_PORT = int(os.getenv("SERVER_PORT", "5000"))
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
