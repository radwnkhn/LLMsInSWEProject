"""ASGI entry point: `uvicorn app.asgi:app`. Reads settings from the environment (and backend/.env)."""
from app.config import load_dotenv
from app.main import create_app
from app.services import services_from_env

load_dotenv()
app = create_app(services_from_env())
