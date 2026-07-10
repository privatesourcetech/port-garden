from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class DockerPort:
    container_id: str
    container: str
    image: str
    status: str
    network_mode: str
    exposed_ports: str
    protocol: str
    container_port: int
    host_ip: str
    host_port: int
    local_url: str

def run_ssh_command(
    host: str,
    username: str,
    command: str,
    ssh_port: int = 22,
) -> str:
    """Run a command on the TrueNAS server over SSH."""

    ssh_command = [
        "ssh",
        "-p",
        str(ssh_port),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        f"{username}@{host}",
        command,
    ]

    result = subprocess.run(
        ssh_command,
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip()

        raise RuntimeError(
            f"SSH command failed:\n{error or 'Unknown SSH error'}"
        )

    return result.stdout

def build_local_url(
    server_host: str,
    host_port: int,
    protocol: str,
) -> str:
    """Return a likely local web URL, or an empty string."""

    if protocol.lower() != "tcp":
        return ""

    non_web_ports = {
        22,
        53,
        445,
        5432,
        6379,
        9987,
        10022,
        11434,
        30033,
        51820,
    }

    if host_port in non_web_ports:
        return ""

    scheme = "https" if host_port in {443, 8443, 9443, 8971} else "http"

    return f"{scheme}://{server_host}:{host_port}"

def fetch_docker_ports(
    host: str,
    username: str,
    ssh_port: int = 22,
) -> list[DockerPort]:
    """Retrieve all published Docker ports from TrueNAS."""

    remote_command = (
        "container_ids=$(sudo -n /usr/bin/docker ps -aq); "
        'if [ -z "$container_ids" ]; then '
        "printf '[]'; "
        "else "
        'printf "%s\\n" "$container_ids" | '
        "xargs sudo -n /usr/bin/docker inspect; "
        "fi"
    )

    raw_output = run_ssh_command(
        host=host,
        username=username,
        command=remote_command,
        ssh_port=ssh_port,
    )

    try:
        containers = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "TrueNAS returned invalid Docker JSON."
        ) from exc

    records: list[DockerPort] = []

    for container in containers:
        container_id = container.get("Id", "")
        container_name = container.get("Name", "").lstrip("/")
        image = container.get("Config", {}).get("Image", "")
        status = container.get("State", {}).get("Status", "")

        network_mode = (
            container
            .get("HostConfig", {})
            .get("NetworkMode", "")
        )

        configured_exposed_ports = (
            container
            .get("Config", {})
            .get("ExposedPorts", {})
            or {}
        )

        exposed_ports = ", ".join(
            sorted(configured_exposed_ports.keys())
        )

        ports = (
            container
            .get("NetworkSettings", {})
            .get("Ports", {})
        )

        configured_port_bindings = (
            container
            .get("HostConfig", {})
            .get("PortBindings", {})
            or {}
        )

        published_record_found = False

        for internal_spec, bindings in ports.items():
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

                published_record_found = True

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
                            server_host=host,
                            host_port=host_port,
                            protocol=protocol,
                        ),
                    )
                )

        if not published_record_found:
            configured_record_found = False

            for internal_spec, bindings in configured_port_bindings.items():
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

                    configured_record_found = True

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
                                server_host=host,
                                host_port=host_port,
                                protocol=protocol,
                            ),
                        )
                    )

            if not configured_record_found:
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

    return sorted(
        records,
        key=lambda record: (
            record.container.lower(),
            record.host_port,
            record.protocol,
        ),
    )


def export_ports_csv(
    records: list[DockerPort],
    output_path: Path,
) -> Path:
    """Write Docker port records to a CSV file."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "container_id",
        "container",
        "image",
        "status",
        "network_mode",
        "exposed_ports",
        "protocol",
        "container_port",
        "host_ip",
        "host_port",
        "local_url",
    ]

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for record in records:
            writer.writerow(asdict(record))

    return output_path