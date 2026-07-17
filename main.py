from __future__ import annotations

import os
import sys
import traceback

from src.bootstrap import create_ok_application
from src.config import build_config


def main() -> None:
    config_folder = "configs"
    if getattr(sys, "frozen", False):
        executable_dir = os.path.dirname(sys.executable)
        os.chdir(sys._MEIPASS)
        config_folder = os.path.join(executable_dir, "configs")

    application = create_ok_application(build_config(config_folder=config_folder))
    application.start()


if __name__ == "__main__":
    try:
        main()
    except Exception as exception:
        base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
        error_path = os.path.join(base_dir, "error.log")
        with open(error_path, "w", encoding="utf-8") as error_file:
            error_file.write(f"Error: {exception}\n\n")
            traceback.print_exc(file=error_file)
        raise
