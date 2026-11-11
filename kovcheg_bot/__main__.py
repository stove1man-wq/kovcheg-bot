import asyncio
import logging

from .config import Config
from .telegram_app import run

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
asyncio.run(run(Config.from_env()))
