from __future__ import annotations

from pathlib import Path

from nicegui import run, ui

from service_overrides import SERVICE_OVERRIDES

from providers.socket_provider import DockerSocketProvider

from settings import (
    DOCKER_HOST_ADDRESS,
    SSH_HOST,
    SSH_PORT,
    SSH_USERNAME,
    WEB_HOST,
    WEB_PORT,
)

from services.docker_inventory import (
    DockerPort,
    export_ports_csv,
)

docker_provider = DockerSocketProvider(
    host_address=DOCKER_HOST_ADDRESS,
)

OUTPUT_DIRECTORY = Path(__file__).parent / "output"
CSV_PATH = OUTPUT_DIRECTORY / "docker_ports.csv"

docker_records: list[DockerPort] = []
last_scan_summary = {
    "total": 0,
    "running": 0,
    "stopped": 0,
    "services": 0,
}
dark = ui.dark_mode(value=True)

columns = [
    {
        "name": "container",
        "label": "Container",
        "field": "container",
        "sortable": True,
        "align": "left",
    },
    {
        "name": "image",
        "label": "Image",
        "field": "image",
        "sortable": True,
        "align": "left",
    },
    {
        "name": "status",
        "label": "Status",
        "field": "status",
        "sortable": True,
        "align": "left",
    },
    {
        "name": "protocol",
        "label": "Protocol",
        "field": "protocol",
        "sortable": True,
        "align": "left",
    },
    {
        "name": "container_port",
        "label": "Container Port",
        "field": "container_port",
        "sortable": True,
    },
    {
        "name": "host_ip",
        "label": "Host IP",
        "field": "host_ip",
        "sortable": True,
        "align": "left",
    },
    {
        "name": "host_port",
        "label": "Host Port",
        "field": "host_port",
        "sortable": True,
    },
    {
        "name": "local_url",
        "label": "Local URL",
        "field": "local_url",
        "sortable": True,
        "align": "left",
    },
    {
        "name": "network_mode",
        "label": "Network Mode",
        "field": "network_mode",
        "sortable": True,
        "align": "left",
    },
    {
        "name": "exposed_ports",
        "label": "Exposed Ports",
        "field": "exposed_ports",
        "sortable": True,
        "align": "left",
    },
]

def get_service_override(container_name: str) -> dict:
    name = container_name.lower()

    for key, override in SERVICE_OVERRIDES.items():
        if key.lower() in name:
            return override

    return {}


def is_web_service(record: DockerPort) -> bool:
    override = get_service_override(record.container)

    if override.get("enabled") is False:
        return False

    return bool(
        override.get("url")
        or record.local_url
    )

async def scan_docker() -> None:
    scan_button.disable()
    status_label.set_text("Connecting to TrueNAS...")

    try:
        records = await run.io_bound(
            docker_provider.fetch,
        )

        docker_records.clear()
        docker_records.extend(records)

        container_names = {
            record.container
            for record in records
        }

        running_names = {
            record.container
            for record in records
            if record.status.lower() == "running"
        }

        stopped_names = container_names - running_names

        web_service_names = {
            record.container
            for record in records
            if record.local_url
        }

        last_scan_summary["total"] = len(container_names)
        last_scan_summary["running"] = len(running_names)
        last_scan_summary["stopped"] = len(stopped_names)
        last_scan_summary["services"] = len(web_service_names)

        scan_summary.refresh()
        docker_cards.refresh()

        table.rows = [
            {
                "container_id": record.container_id[:12],
                "container": record.container,
                "image": record.image,
                "status": record.status,
                "protocol": record.protocol,
                "container_port": record.container_port,
                "host_ip": record.host_ip,
                "host_port": record.host_port,
                "local_url": record.local_url,
                "network_mode": record.network_mode,
                "exposed_ports": record.exposed_ports,
            }
            for record in records
        ]

        table.update()

        status_label.set_text(
            f"Found {len(records)} published port mappings."
        )

        ui.notify(
            "Docker inventory updated",
            type="positive",
        )

    except Exception as exc:
        status_label.set_text("Docker scan failed.")

        ui.notify(
            str(exc),
            type="negative",
            timeout=10000,
            close_button=True,
        )

    finally:
        scan_button.enable()


async def save_csv() -> None:
    if not docker_records:
        ui.notify(
            "Scan Docker before exporting the CSV.",
            type="warning",
        )
        return

    try:
        output_path = await ui.run_cpu_bound(
            export_ports_csv,
            docker_records,
            CSV_PATH,
        )

        ui.notify(
            f"CSV saved to {output_path}",
            type="positive",
            timeout=7000,
        )

    except Exception as exc:
        ui.notify(
            str(exc),
            type="negative",
            timeout=10000,
            close_button=True,
        )

@ui.refreshable
def scan_summary() -> None:
    with ui.row().classes(
        "w-full gap-3 flex-wrap"
    ):
        summary_items = [
            (
                "Containers",
                last_scan_summary["total"],
                "inventory_2",
                "text-sky-400",
            ),
            (
                "Running",
                last_scan_summary["running"],
                "check_circle",
                "text-emerald-400",
            ),
            (
                "Stopped",
                last_scan_summary["stopped"],
                "cancel",
                "text-red-400",
            ),
            (
                "Web Services",
                last_scan_summary["services"],
                "language",
                "text-violet-400",
            ),
        ]

        for label, value, icon, icon_class in summary_items:
            with ui.card().classes(
                "min-w-44 flex-1 "
                "bg-slate-900/60 border border-white/10 "
                "shadow-sm"
            ):
                with ui.row().classes(
                    "items-center justify-between w-full"
                ):
                    with ui.column().classes("gap-0"):
                        ui.label(label).classes(
                            "text-xs uppercase tracking-wider "
                            "text-slate-400"
                        )

                        ui.label(str(value)).classes(
                            "text-2xl font-bold text-white"
                        )

                    ui.icon(icon).classes(
                        f"text-3xl {icon_class}"
                    )

ui.page_title("Port Garden")

with ui.header().classes(
    "items-center px-6 py-3 "
    "bg-gradient-to-r from-emerald-900 via-slate-900 to-slate-950 "
    "border-b border-emerald-500/20 shadow-lg"
):
    with ui.row().classes("items-center gap-3"):
        with ui.element("div").classes(
            "w-11 h-11 rounded-xl "
            "bg-emerald-500/15 border border-emerald-400/30 "
            "flex items-center justify-center"
        ):
            ui.icon("yard").classes("text-emerald-400 text-2xl")

        with ui.column().classes("gap-0"):
            ui.label("Port Garden").classes(
                "text-xl font-bold tracking-wide text-white"
            )

            ui.label(
                "Your local services, all in one place"
            ).classes(
                "text-xs text-slate-400"
            )

    ui.space()

    with ui.row().classes("items-center gap-3"):
        with ui.element("div").classes(
            "hidden md:flex items-center gap-2 "
            "px-3 py-2 rounded-lg "
            "bg-white/5 border border-white/10"
        ):
            ui.icon("dns").classes("text-emerald-400")

            ui.label(DOCKER_HOST_ADDRESS).classes(
                "text-sm text-slate-200 font-medium"
            )

        dark_button = ui.button(
            icon="dark_mode",
            on_click=lambda: dark.toggle(),
        ).props(
            "flat round"
        ).classes(
            "text-white bg-white/10 hover:bg-white/20"
        )

        dark_button.tooltip("Toggle dark mode")

with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-6"):
    ui.label("Docker Tools").classes("text-3xl font-bold")

    scan_summary()

    with ui.card().classes("w-full"):
        ui.label("Docker Port Inventory").classes("text-xl font-semibold")
        ui.label(
            "Read published Docker ports from TrueNAS over SSH."
        ).classes("text-gray-500")

        with ui.row().classes(
            "items-center gap-3 w-full"
        ):
            scan_button = ui.button(
                "Scan Docker",
                icon="refresh",
                on_click=scan_docker,
            ).props(
                "unelevated"
            ).classes(
                "bg-emerald-600 hover:bg-emerald-500 "
                "text-white font-medium"
            )

            ui.button(
                "Export CSV",
                icon="download",
                on_click=save_csv,
            ).props(
                "outline"
            ).classes(
                "text-slate-200 border-slate-600"
            )

            ui.space()

            status_label = ui.label(
                "Docker has not been scanned yet."
            ).classes(
                "text-sm text-slate-400"
            )


    def choose_web_record(records: list[DockerPort]) -> DockerPort | None:
        """Choose the most likely browser-accessible port for one container."""

        non_web_container_ports = {
            22,      # SSH
            53,      # DNS
            445,     # SMB
            5432,    # PostgreSQL
            6379,    # Redis
            8554,    # RTSP
            8555,    # WebRTC/streaming
            9987,    # TeamSpeak voice
            10022,   # TeamSpeak SSH/query
            11434,   # Ollama API
            30033,   # TeamSpeak file transfer
            51820,   # WireGuard
        }

        preferred_container_ports = [
            80,
            8080,
            3000,
            3001,
            5000,
            5055,
            6767,
            7878,
            8096,
            8265,
            8686,
            8971,
            8989,
            9696,
            443,
            8443,
            9443,
        ]

        candidates = [
            record
            for record in records
            if record.protocol.lower() == "tcp"
            and record.local_url
            and record.container_port not in non_web_container_ports
        ]

        if not candidates:
            return None

        def score(record: DockerPort) -> tuple[int, int]:
            try:
                preference = preferred_container_ports.index(
                    record.container_port
                )
            except ValueError:
                preference = len(preferred_container_ports)

            return preference, record.host_port

        return min(candidates, key=score)
    
    def find_shared_network_record(
        record: DockerPort,
        all_records: list[DockerPort],
    ) -> DockerPort | None:
        """Resolve network_mode container:<id> through the provider container."""

        if not record.network_mode.startswith("container:"):
            return None

        provider_id = record.network_mode.split(":", 1)[1]

        exposed_tcp_ports = set(
            parse_exposed_tcp_ports(record.exposed_ports)
        )

        provider_records = [
            candidate
            for candidate in all_records
            if candidate.container_id.startswith(provider_id)
            and candidate.protocol.lower() == "tcp"
            and candidate.local_url
        ]

        matching_records = [
            candidate
            for candidate in provider_records
            if candidate.container_port in exposed_tcp_ports
        ]

        if matching_records:
            return choose_web_record(matching_records)

        if len(provider_records) == 1:
            return provider_records[0]

        return None
    
    def parse_exposed_tcp_ports(exposed_ports: str) -> list[int]:
        ports: list[int] = []

        for value in exposed_ports.split(","):
            value = value.strip()

            if not value.endswith("/tcp"):
                continue

            port_text = value.removesuffix("/tcp")

            try:
                ports.append(int(port_text))
            except ValueError:
                continue

        return ports


    def build_host_network_url(record: DockerPort) -> str:
        """Build a URL for a host-network container from declared exposed ports."""

        exposed_tcp_ports = parse_exposed_tcp_ports(record.exposed_ports)

        non_web_ports = {
            22,
            53,
            445,
            5432,
            6379,
            8554,
            8555,
            9987,
            10022,
            11434,
            30033,
            51820,
        }

        candidates = [
            port
            for port in exposed_tcp_ports
            if port not in non_web_ports
        ]

        if not candidates:
            return ""

        preferred_ports = [
            80,
            443,
            3000,
            3001,
            5000,
            5055,
            6767,
            7878,
            8080,
            8096,
            8265,
            8686,
            8971,
            8989,
            9443,
            9696,
            32400,
        ]

        selected_port = min(
            candidates,
            key=lambda port: (
                preferred_ports.index(port)
                if port in preferred_ports
                else len(preferred_ports),
                port,
            ),
        )

        scheme = "https" if selected_port in {
            443,
            8443,
            8971,
            9443,
        } else "http"

        return f"{scheme}://{DOCKER_HOST_ADDRESS}:{selected_port}"

    @ui.refreshable
    def docker_cards() -> None:
        search_text = (
            service_search.value.strip().lower()
            if service_search.value
            else ""
        )

        records_by_container: dict[str, list[DockerPort]] = {}

        for record in docker_records:
            records_by_container.setdefault(
                record.container,
                [],
            ).append(record)

        service_cards: list[tuple[str, DockerPort, str]] = []

        for container_name, records in records_by_container.items():
            if search_text and search_text not in container_name.lower():
                continue
            override = get_service_override(container_name)

            if override.get("enabled") is False:
                continue

            representative = records[0]
            selected_record = choose_web_record(records)
            url = ""

            if selected_record is not None:
                url = selected_record.local_url

            elif representative.network_mode == "host":
                url = build_host_network_url(representative)
                selected_record = representative

            elif representative.network_mode.startswith("container:"):
                selected_record = find_shared_network_record(
                    representative,
                    docker_records,
                )

                if selected_record is not None:
                    url = selected_record.local_url

            override_url = override.get("url")

            if override_url:
                url = override_url

            if not url or selected_record is None:
                continue

            title = override.get(
                "title",
                container_name,
            )

            service_cards.append(
                (title, selected_record, url)
            )

        service_cards.sort(
            key=lambda item: item[0].lower()
        )

        if not service_cards:
            ui.label(
                "Scan Docker to populate service cards."
            ).classes("text-gray-500")
            return

        with ui.row().classes("w-full gap-4"):
            for title, record, url in service_cards:
                is_running = record.status.lower() == "running"

                card_classes = (
                    "w-72 border-2 border-green-600 bg-green-950/20"
                    if is_running
                    else "w-72 border-2 border-red-600 bg-red-950/20"
                )

                is_running = record.status.lower() == "running"

                card_classes = (
                    "w-72 border-2 border-green-600 bg-green-950/20"
                    if is_running
                    else "w-72 border-2 border-red-600 bg-red-950/20"
                )

                with ui.card().classes(card_classes):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon(
                            "check_circle" if is_running else "cancel"
                        ).classes(
                            "text-green-500"
                            if is_running
                            else "text-red-500"
                        )

                        ui.label(record.status.upper()).classes(
                            "text-sm font-bold "
                            + (
                                "text-green-500"
                                if is_running
                                else "text-red-500"
                            )
                        )

                    ui.label(title).classes(
                        "text-lg font-semibold"
                    )

                    ui.label(record.image).classes(
                        "text-xs text-gray-500 break-all"
                    )

                    if record.host_port:
                        ui.label(
                            f"TCP {record.host_port} → "
                            f"{record.container_port}"
                        ).classes("text-sm")
                    else:
                        ui.label(
                            f"Network mode: {record.network_mode}"
                        ).classes("text-sm")

                    ui.label(url).classes(
                        "text-xs text-gray-500 break-all"
                    )

                    ui.button(
                        "Open",
                        icon="open_in_new",
                        on_click=lambda url=url:
                            ui.navigate.to(url, new_tab=True),
                    )


    ui.label("Docker Services").classes(
        "text-2xl font-bold"
    )

    service_search = ui.input(
        placeholder="Search containers..."
    ).props("clearable outlined dense").classes("w-full max-w-md")

    docker_cards()

    service_search.on(
        "update:model-value",
        lambda: docker_cards.refresh(),
    )

    table = ui.table(
        columns=columns,
        rows=[],
        row_key="container",
        pagination=25,
    ).classes("w-full")

    table.add_slot(
        "body-cell-local_url",
        r"""
        <q-td :props="props">
            <a
                v-if="props.value"
                :href="props.value"
                target="_blank"
                rel="noopener noreferrer"
                class="text-primary underline"
            >
                {{ props.value }}
            </a>
        </q-td>
        """,
    )

ui.run(
    title="Port Garden",
    host=WEB_HOST,
    port=WEB_PORT,
    reload=False,
)