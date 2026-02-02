# EdgeFlow

**A Lightweight Framework for Distributed Edge AI Pipelines**

EdgeFlow is a framework for building real-time video processing pipelines with ease.

Scale horizontally to increase FPS linearly with the number of nodes. Deploy to Kubernetes with a single `edgeflow up` command—build, push, and deploy all automated. Overcome the performance limits of a single device through distributed processing.

[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](pyproject.toml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

[🇺🇸 English](README.md) | [🇰🇷 한국어](docs/README_kr.md) | [📖 Technical Deep Dive](docs/TECHNICAL_DEEP_DIVE.md)

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **Arduino-Style API** | Intuitive node development with `setup()` / `loop()` pattern |
| **Fluent Wiring DSL** | Define pipelines with `app.link(cam).to(gpu).to(gw)` chaining |
| **QoS-based Streaming** | REALTIME (latest only) / DURABLE (sequential) consumption modes |
| **Protocol Abstraction** | Auto-select Redis / TCP, user code is protocol-agnostic |
| **Kubernetes Ready** | Auto-generate K8s manifests with `edgeflow up` |
| **Hot Reload (sync)** | Push code changes to running pods without rebuild |
| **Web Dashboard** | Real-time video streams and metrics monitoring |

---

## 🛠 Installation

```bash
# 1. Install uv
pip install uv

# 2. Install edgeflow CLI globally
uv tool install git+https://github.com/seolgugu/edgeflow.git

# 3. Verify installation
edgeflow --help
```

---

## 🚀 Quick Start (Local)

### 1. Clone Repository

```bash
git clone https://github.com/seolgugu/edgeflow.git
cd edgeflow
```

### 2. Start Redis

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### 3. Run Example

```bash
edgeflow local examples/tutorial/main.py
```

### 4. Access Dashboard

Open `http://localhost:8000/dashboard` in your browser.

---

## 📝 Example Code (`main.py`)

```python
from edgeflow import System, QoS
from edgeflow.comms import RedisListBroker

# Define System
app = System("tutorial", broker=RedisListBroker())

# Register Nodes
cam = app.node("nodes/camera", fps=30)
yolo = app.node("nodes/yolo", replicas=2)
gw = app.node("nodes/gateway", node_port=30080)

# Wire Pipeline
app.link(cam).to(yolo, qos=QoS.REALTIME).to(gw)  # AI stream
app.link(cam).to(gw)                              # Raw stream

# Run
if __name__ == "__main__":
    app.run()
```

---

## ☸️ Deploy to Kubernetes

For Kubernetes deployment, see: **[K8s Deployment Guide](docs/getting_started_k8s_kr.md)**

```bash
edgeflow up main.py --registry docker.io/yourusername --arch linux/arm64
```

---

## 🖥 CLI Commands

| Command | Description |
|---------|-------------|
| `local` | Run locally with uv |
| `up` | Build, Push, Deploy (All-in-one) |
| `sync` | Hot reload code to running pods |
| `logs` | View node logs from K8s |
| `clean` | Clean up namespace resources |
| `doctor` | Check environment health |

---

## 💡 Design Highlights

### `link.to()` Chaining

```python
app.link(cam).to(yolo).to(gw)  # Camera → YOLO → Gateway
```

### QoS-based Consumption

```python
app.link(cam).to(yolo, qos=QoS.REALTIME)   # Latest frame only
app.link(cam).to(logger, qos=QoS.DURABLE)  # All frames sequentially
```

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [**K8s Getting Started**](docs/getting_started_k8s_kr.md) | Kubernetes deployment guide |
| [**Technical Deep Dive**](docs/TECHNICAL_DEEP_DIVE.md) | Core design philosophy |
| [**한국어 README**](docs/README_kr.md) | Korean documentation |

---

## License

Apache 2.0 License - see [LICENSE](LICENSE) file for details.
