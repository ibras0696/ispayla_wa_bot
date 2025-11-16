from __future__ import annotations

import logging

from .bot import create_bot
from .config import get_settings


logger = logging.getLogger("app.bot")
logging.basicConfig(level=logging.INFO)


def main() -> None:
    settings = get_settings()
    bot = create_bot(settings)
    logger.info("Запускаем бота Green API (инстанс %s).", settings.id_instance)
    bot.run_forever()


if __name__ == "__main__":
    main()
