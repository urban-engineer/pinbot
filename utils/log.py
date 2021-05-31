import json
import logging.config
import typing

from utils import config


# Stack level 0 displays the information of the log message function
# Stack level 1 displays the information of the log message function
# Stack level 2 displays the information of the function that called the log message function
# Stack level 3 displays the information of the function that called the function that called the log message function
# [repeat "the function that called" as stack level increases]
STACK_LEVEL_CURRENT_FUNCTION = 1
STACK_LEVEL_DEFAULT = 2
STACK_LEVEL_PREVIOUS = 3
STACK_LEVEL_PREVIOUS_PREVIOUS = 4


logging_config_file = config.get_config_directory().joinpath("logging.json")
logging.config.dictConfig(json.loads(logging_config_file.read_text()))
importer_logger = logging.getLogger("importer_logger")

# I don't care for requests debug output, if I need that info it's because I'm passing bad info to the module.
logging.getLogger("urllib3").setLevel(logging.INFO)
logging.getLogger("chardet").setLevel(logging.INFO)


def debug(message: typing.Any, stack_level: int = STACK_LEVEL_DEFAULT) -> None:
    importer_logger.debug(str(message), stacklevel=stack_level)


def info(message: typing.Any, stack_level: int = STACK_LEVEL_DEFAULT) -> None:
    importer_logger.info(str(message), stacklevel=stack_level)


def warning(message: typing.Any, stack_level: int = STACK_LEVEL_DEFAULT) -> None:
    importer_logger.warning(str(message), stacklevel=stack_level)


def error(message: typing.Any, stack_level: int = STACK_LEVEL_DEFAULT) -> None:
    importer_logger.error(str(message), stacklevel=stack_level)


def critical(message: typing.Any, stack_level: int = STACK_LEVEL_DEFAULT) -> None:
    importer_logger.critical(str(message), stacklevel=stack_level)
