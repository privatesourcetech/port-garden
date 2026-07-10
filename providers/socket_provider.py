from __future__ import annotations

import docker

from providers.base import DockerProvider
from services.docker_inventory import DockerPort, build_local_url

class DockerSocketProvider(DockerProvider):
    """Read Docker inventory directly through the local Docker socket."""

    def __init__(self, host_address: str) -> None:
        self.client = docker.from_env()
        self.host_address = host_address

    def fetch(self) -> list[DockerPort]:
        containers = self.client.containers.list(all=True)

        records: list[DockerPort] = []

        for container in containers:
            container.reload()
            attrs = container.attrs

            container_id = attrs.get("Id", "")
            container_name = attrs.get("Name", "").lstrip("/")
            image = attrs.get("Config", {}).get("Image", "")
            status = attrs.get("State", {}).get("Status", "")
            network_mode = attrs.get("HostConfig", {}).get(
                "NetworkMode",
                "",
            )

            exposed = (
                attrs.get("Config", {}).get("ExposedPorts", {})
                or {}
            )

            exposed_ports = ", ".join(sorted(exposed.keys()))

            live_ports = (
                attrs.get("NetworkSettings", {}).get("Ports", {})
                or {}
            )

            configured_ports = (
                attrs.get("HostConfig", {}).get("PortBindings", {})
                or {}
            )

            source_ports = live_ports if any(live_ports.values()) else configured_ports
            found_port = False

            for internal_spec, bindings in source_ports.items():
                if not bindings:
                    continue

                try:
                    internal_port_text, protocol = internal_spec.split("/", 1)
                    internal_port = int(internal_port_text)
                except ValueError:
                    continue

                for binding in bindings:
                    host_port_text = binding.get("HostPort")

                    try:
                        host_port = int(host_port_text)
                    except (TypeError, ValueError):
                        continue

                    found_port = True

                    records.append(
                        DockerPort(
                            container_id=container_id,
                            container=container_name,
                            image=image,
                            status=status,
                            network_mode=network_mode,
                            exposed_ports=exposed_ports,
                            protocol=protocol,
                            container_port=internal_port,
                            host_ip=binding.get("HostIp", ""),
                            host_port=host_port,
                            local_url=build_local_url(
                                server_host=self.host_address,
                                host_port=host_port,
                                protocol=protocol,
                            ),
                        )
                    )

            if not found_port:
                records.append(
                    DockerPort(
                        container_id=container_id,
                        container=container_name,
                        image=image,
                        status=status,
                        network_mode=network_mode,
                        exposed_ports=exposed_ports,
                        protocol="",
                        container_port=0,
                        host_ip="",
                        host_port=0,
                        local_url="",
                    )
                )

        return records