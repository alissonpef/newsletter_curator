from __future__ import annotations

import uvicorn
from dotenv import load_dotenv

from hermes.infra.container import build_container
from hermes.infra.web.server import ServerConfig, app


def main():
    load_dotenv()

    container = build_container()

    ServerConfig.state_repo = container.state_repo
    ServerConfig.process_daily_uc = container.process_daily_uc
    ServerConfig.send_to_kindle_uc = container.send_to_kindle_uc
    ServerConfig.search_uc = container.search_uc
    ServerConfig.days_back = container.web_days_back
    ServerConfig.default_kindle_email = container.kindle_address
    ServerConfig.kindle_enabled = container.kindle_enabled

    print(f"Starting Hermes Server on {container.web_host}:{container.web_port}")
    uvicorn.run(app, host=container.web_host, port=container.web_port)


if __name__ == "__main__":
    main()
