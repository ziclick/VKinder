import tomllib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
config_path = BASE_DIR / "config.toml"
config = tomllib.loads(config_path.read_text())
DB = config["DB"]
HOST = DB["HOST"]
USER = DB["USER"]
PASSWORD = DB["PASSWORD"]
DATABASE = DB["DATABASE"]

ACCESS = config["ACCESS"]
USER_TOKEN = ACCESS["USER_TOKEN"]
GROUP_TOKEN = ACCESS["GROUP_TOKEN"]

print("Config loaded\n"
      "HOST: {}\n"
      "USER: {}\n"
      "PASSWORD: {}\n"
      "DATABASE: {}\n"
      "USER_TOKEN: {}\n"
      "GROUP_TOKEN: {}\n".format(
    HOST, USER, PASSWORD, DATABASE, USER_TOKEN, GROUP_TOKEN
)
)
