"""Entry point for running the custom connector service."""

import os
import sys
from connector import CustomSourceConnector


def main() -> None:
    host = os.getenv("CONNECTOR_HOST", "0.0.0.0")
    port = int(os.getenv("CONNECTOR_PORT", "8080"))
    token = os.getenv("CONNECTOR_AUTH_TOKEN")
    log_level = os.getenv("LOG_LEVEL", "info")

    print(f"Starting Stovo Connector service on {host}:{port}...")
    if not token:
        print("WARNING: CONNECTOR_AUTH_TOKEN is not set. Service is unauthenticated!", file=sys.stderr)

    CustomSourceConnector.serve(
        host=host,
        port=port,
        auth_token=token,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
