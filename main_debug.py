from __future__ import annotations

from src.bootstrap import create_ok_application
from src.config import build_config

if __name__ == "__main__":
    application = create_ok_application(build_config(debug=True))
    application.start()
