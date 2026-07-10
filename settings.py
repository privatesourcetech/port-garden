from __future__ import annotations

import os


DOCKER_MODE = os.getenv(
    "PORT_GARDEN_DOCKER_MODE",
    "ssh",
).strip().lower()

DOCKER_HOST_ADDRESS = os.getenv(
    "PORT_GARDEN_HOST_ADDRESS",
    "127.0.0.1",
).strip()

WEB_HOST = os.getenv(
    "PORT_GARDEN_WEB_HOST",
    "127.0.0.1",
).strip()

WEB_PORT = int(
    os.getenv(
        "PORT_GARDEN_WEB_PORT",
        "8080",
    )
)
SSH_HOST = os.getenv(
    "PORT_GARDEN_SSH_HOST",
    DOCKER_HOST_ADDRESS,
).strip()

SSH_USERNAME = os.getenv(
    "PORT_GARDEN_SSH_USERNAME",
    "admin",
).strip()

SSH_PORT = int(
    os.getenv(
        "PORT_GARDEN_SSH_PORT",
        "22",
    )
)

