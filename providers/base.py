from __future__ import annotations

from abc import ABC, abstractmethod

from services.docker_inventory import DockerPort


class DockerProvider(ABC):
    """Common interface for retrieving Docker container information."""

    @abstractmethod
    def fetch(self) -> list[DockerPort]:
        """Return Docker container and port records."""
        raise NotImplementedError