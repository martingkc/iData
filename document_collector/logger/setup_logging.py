import logging.config

import pathlib
import os
import atexit
import json


def setup_logging(path: str | None = None) -> None:
    if path is None:
        path = os.environ.get(
            "LOGGING_CONFIG_PATH", os.path.join("configs", "logger_config.json")
        )
    config_file = None
    config_file = pathlib.Path(path)
    with open(config_file) as f_in:
        config = json.load(f_in)

    logging.config.dictConfig(config)
    queue_handler = logging.getHandlerByName("queue_handler")
    if queue_handler is not None:
        queue_handler.listener.start()
        atexit.register(queue_handler.listener.stop)
