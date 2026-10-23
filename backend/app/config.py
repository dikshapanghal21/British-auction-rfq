##..

import os
from pathlib import Path

from dotenv import load_dotenv #env loader

load_dotenv(Path(__file__).resolve().parent.parent / ".env") 

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/british_auction") #fallback url
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()] #allowed origins
SWEEPER_ENABLED = os.getenv("SWEEPER_ENABLED", "1") != "0" #on by default!!
SWEEP_INTERVAL_SECONDS = float(os.getenv("SWEEP_INTERVAL_SECONDS", "1")) #every second.


