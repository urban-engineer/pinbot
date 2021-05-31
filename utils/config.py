import json
import pathlib


def get_config_directory() -> pathlib.Path:
    """
    Get the path to the config directory based off its location to this file.  Up two directories, then into config

    :return: Path pointing to the config directory
    """
    return pathlib.Path(__file__).absolute().parent.parent.joinpath("config")


def load_secret_configs() -> dict:
    return json.loads(get_config_directory().joinpath("secrets.json").read_text())


def load_discord_token() -> str:
    return load_secret_configs()["bot_token"]
