# Port Garden

**A lightweight homelab dashboard for discovering and opening locally hosted Docker services.**

Port Garden connects to a Docker host, discovers containers and their published ports, and presents browser-accessible services as searchable, status-colored cards.

The project is built with Python and [NiceGUI](https://nicegui.io/).

> Port Garden is currently under active development. The present version uses SSH to inspect Docker on a remote host. A direct Docker socket deployment and prebuilt container image are planned.

---

## Features

* Discover running and stopped Docker containers
* Read live and configured Docker port mappings
* Generate local service URLs automatically
* Display one card per detected web service
* Show running services in green
* Show stopped services in red
* Keep stopped containers visible using configured port bindings
* Search and filter service cards
* Open services directly in a new browser tab
* Display raw Docker inventory in a sortable table
* Export the Docker inventory to CSV
* Detect:

  * Published Docker ports
  * Host-network containers
  * Containers sharing another container's network namespace
  * Declared exposed ports
* Light and dark themes
* Dark mode enabled by default
* Optional service-specific URL overrides

---

## Screenshots

Screenshots will be added as the interface develops.

---

## Current Architecture

Port Garden currently runs as a local Python application and connects to a Docker host over SSH.

```text
Browser
   |
   v
Port Garden / NiceGUI
   |
   v
SSH connection
   |
   v
Docker host
   |
   v
docker inspect
```

The application reads Docker metadata but does not currently start, stop, restart, or modify containers.

---

## Requirements

### Local development computer

* Python 3.12
* OpenSSH client
* Git
* A modern web browser

### Docker host

* Docker
* SSH access
* An SSH account permitted to run Docker inspection commands
* SSH key authentication

The current implementation expects the Docker host account to run Docker through passwordless `sudo`.

Example command used by Port Garden:

```bash
sudo -n /usr/bin/docker ps -aq
```

The Docker executable path may differ on other systems.

---

## Installation

Clone the repository:

```bash
git clone git@github.com:privatesourcetech/port-garden.git
cd port-garden
```

Create a Python 3.12 virtual environment:

```bash
python3.12 -m venv venv312
```

Activate it:

```bash
source venv312/bin/activate
```

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## Configuration

Create a local `config.py` file in the repository root:

```python
TRUENAS_HOST = "192.168.1.171"
TRUENAS_USERNAME = "admin"
TRUENAS_SSH_PORT = 22
```

Replace the values with the address and account for your Docker host.

The local `config.py` file should not be committed to Git.

Make sure `.gitignore` contains:

```gitignore
config.py
output/
venv312/
__pycache__/
*.py[cod]
```

---

## SSH Setup

Port Garden uses non-interactive SSH authentication.

Create an SSH key if needed:

```bash
ssh-keygen -t ed25519
```

Copy it to the Docker host:

```bash
ssh-copy-id admin@192.168.1.171
```

Test passwordless SSH:

```bash
ssh -o BatchMode=yes admin@192.168.1.171 'echo SUCCESS'
```

Test Docker access:

```bash
ssh -o BatchMode=yes admin@192.168.1.171 \
  'sudo -n /usr/bin/docker ps'
```

Both commands must work without prompting for a password.

### TrueNAS SCALE

For the configured SSH user, allow passwordless execution of:

```text
/usr/bin/docker
```

Use the TrueNAS user-management interface to grant only the required command rather than unrestricted passwordless sudo.

---

## Running Port Garden

Activate the virtual environment:

```bash
source venv312/bin/activate
```

Start the application:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:8080
```

Click **Scan Docker** to populate the service cards and inventory table.

---

## Service Discovery

Port Garden attempts to identify browser-accessible services from Docker metadata.

It examines:

* `NetworkSettings.Ports`
* `HostConfig.PortBindings`
* `HostConfig.NetworkMode`
* `Config.ExposedPorts`
* Container status
* Container image and name

For a typical Compose mapping:

```yaml
ports:
  - "4001:8989"
```

Port Garden generates:

```text
http://DOCKER-HOST:4001
```

If the Compose host port changes, the next Docker scan should discover the new port automatically.

---

## Service Overrides

Some services cannot be detected reliably from Docker metadata alone.

Common reasons include:

* Host networking
* Custom URL paths
* Multiple web ports
* HTTPS requirements
* Ports not declared by the image
* Services sharing another container's network

Overrides are currently stored in:

```text
service_overrides.py
```

Example:

```python
SERVICE_OVERRIDES = {
    "plex": {
        "enabled": True,
        "title": "Plex",
        "url": "http://192.168.1.171:32400/web",
    },
    "audiobookshelf": {
        "enabled": True,
        "title": "Audiobookshelf",
        "url": "http://192.168.1.171:13378",
    },
    "teamspeak": {
        "enabled": False,
    },
}
```

An explicit URL should only be used when automatic discovery cannot determine the correct address.

Future versions will move overrides into a persistent YAML configuration file and web-based settings page.

---

## CSV Export

After scanning Docker, click **Export CSV**.

The inventory is written to:

```text
output/docker_ports.csv
```

Current CSV fields:

```text
container_id
container
image
status
network_mode
exposed_ports
protocol
container_port
host_ip
host_port
local_url
```

---

## Project Structure

```text
port-garden/
├── app.py
├── config.py
├── service_overrides.py
├── requirements.txt
├── services/
│   ├── __init__.py
│   └── docker_inventory.py
├── output/
│   └── docker_ports.csv
├── .gitignore
└── README.md
```

`config.py`, the virtual environment, generated output, and Python cache files should remain untracked.

---

## Planned Public Deployment

The intended public deployment will follow a Dozzle-style model:

```text
Browser
   |
   v
Port Garden container
   |
   v
Docker API
   |
   v
/var/run/docker.sock
```

Planned Compose usage:

```yaml
services:
  port-garden:
    image: ghcr.io/privatesourcetech/port-garden:latest
    container_name: port-garden
    restart: unless-stopped

    ports:
      - "8090:8080"

    environment:
      PORT_GARDEN_HOST_ADDRESS: "192.168.1.171"

    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./data:/app/data
```

This image is not published yet.

### Docker Socket Security

Mounting:

```text
/var/run/docker.sock
```

gives an application extensive access to the Docker host.

Future documentation will include:

* Direct socket deployment
* Restricted Docker socket proxy deployment
* Optional SSH provider
* Remote-agent support

Do not expose a Docker-socket-enabled dashboard directly to the public internet without authentication and appropriate network protections.

---

## Roadmap

### Initial public release

* Docker socket provider
* SSH provider
* Environment-variable configuration
* Dockerfile
* Public Compose example
* Persistent service overrides
* GitHub Container Registry image
* Automated multi-architecture image builds
* Health check
* Application version display
* Screenshots and installation documentation

### Later features

* Multiple Docker hosts
* Optional remote agent
* Container start, stop, and restart controls
* Service categories
* Custom icons
* Card ordering
* URL health checks
* Favorites
* Authentication
* Reverse-proxy URL support
* Compose project grouping
* Docker event-driven updates
* Settings page
* Import and export configuration
* Responsive mobile layout

---

## Development

Create a feature branch:

```bash
git checkout -b feature/example
```

Run the application:

```bash
python app.py
```

Check changes:

```bash
git status
```

Commit:

```bash
git add .
git commit -m "Describe the change"
git push
```

---

## Status

Port Garden is experimental and under active development.

The current implementation is suitable for trusted local homelab environments. Interfaces, configuration formats, and deployment methods may change before the first tagged release.

---

## License

A license has not yet been selected.

Before publishing the repository publicly, add a license such as MIT or Apache-2.0.
