from dotenv import load_dotenv
import os 

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")