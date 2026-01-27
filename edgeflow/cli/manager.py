# edgeflow/cli/manager.py
"""CLI Manager for managing project dependencies and logs"""

import os
import re
import sys
import subprocess
import shutil
from pathlib import Path


# ==========================================
# 1. Project Management (Add, Init)
# ==========================================

def add_dependency(package: str, node_path: str = None):
    """
    Add a python package to node.toml dependencies.
    If node_path is None, try to find node.toml in current dir or ask user.
    """
    target_file = None
    
    # 1. 경로 자동 추론
    if node_path:
        # 명시적 경로 (예: "nodes/camera")
        path = Path(node_path)
        if path.is_file() and path.name == "node.toml":
            target_file = path
        elif path.is_dir():
            target_file = path / "node.toml"
    else:
        # 현재 디렉토리
        cwd = Path.cwd()
        if (cwd / "node.toml").exists():
            target_file = cwd / "node.toml"
    
    if not target_file or not target_file.exists():
        print(f"❌ Error: Could not find node.toml in '{node_path or 'current directory'}'")
        print("Usage: edgeflow add <package> --node nodes/camera")
        sys.exit(1)

    # 2. 파일 읽기
    content = target_file.read_text(encoding="utf-8")
    
    # 3. 의존성 추가 (Regex 활용)
    # dependencies = ["numpy", "opencv-python"] 패턴 찾기
    dep_pattern = r'(dependencies\s*=\s*\[)(.*?)(\])'
    
    match = re.search(dep_pattern, content, re.DOTALL)
    if match:
        prefix, current_deps, suffix = match.groups()
        
        # 이미 존재하는지 확인
        if f'"{package}"' in current_deps or f"'{package}'" in current_deps:
            print(f"⚠️ Package '{package}' is already in {target_file}")
            return

        # 리스트 끝에 추가
        # 마지막 요소 뒤에 콤마가 있는지 확인하고 처리
        clean_deps = current_deps.strip()
        new_dep = f', "{package}"' if clean_deps and not clean_deps.endswith(',') else f'"{package}"'
        if not clean_deps:
            new_dep = f'"{package}"'
            
        new_content = content.replace(
            match.group(0), 
            f'{prefix}{current_deps}{new_dep}{suffix}'
        )
    else:
        # dependencies 키가 없는 경우 [build] 섹션 아래 추가 필요
        # (간단하게 구현하기 위해 이건 사용자가 직접 포맷을 맞췄다고 가정하거나, [build] 섹션을 찾아 추가)
        print(f"❌ Error: 'dependencies = []' list not found in [build] section.")
        print("Please ensure node.toml has a valid format.")
        sys.exit(1)

    # 4. 저장
    target_file.write_text(new_content, encoding="utf-8")
    print(f"✅ Added '{package}' to {target_file}")


def init_project(project_name: str):
    """
    Initialize a new EdgeFlow project with directory structure and templates.
    """
    base_path = Path(project_name)
    
    if base_path.exists():
        print(f"❌ Error: Directory '{project_name}' already exists.")
        return

    print(f"🔨 Creating project '{project_name}'...")
    base_path.mkdir(parents=True)
    
    # 1. Create Directories
    (base_path / "nodes").mkdir()
    (base_path / "nodes" / "example_node").mkdir()

    # 2. pyproject.toml
    pyproject_content = f"""[project]
name = "{project_name}"
version = "0.1.0"
description = "EdgeFlow Project"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "edgeflow",
]

[tool.uv]
dev-dependencies = []
"""
    (base_path / "pyproject.toml").write_text(pyproject_content, encoding="utf-8")

    # 3. main.py Template
    main_py_content = """from edgeflow import System, QoS
from edgeflow.comms import DualRedisBroker

def main():
    # 1. Define System with Broker
    # DualRedisBroker handles both high-speed streams (Control) and large data (Data)
    broker = DualRedisBroker()
    sys = System("my-edge-system", broker=broker)

    # 2. Register Nodes
    # 'nodes/example_node' folder must contain node.toml and source code
    node_a = sys.node("nodes/example_node", replicas=1)
    
    # 3. Define Pipeline (Link Nodes)
    # sys.link(node_a).to(node_b)
    
    print(f"🚀 System '{sys.name}' is ready. Run with 'edgeflow deploy'!")
    return sys

if __name__ == "__main__":
    main()
"""
    (base_path / "main.py").write_text(main_py_content, encoding="utf-8")

    # 4. nodes/example_node/__init__.py
    node_init_content = """from edgeflow import Node

class ExampleNode(Node):
    def setup(self):
        print(f"[{self.name}] Setup complete!")

    def loop(self, data):
        # Process data here
        print(f"[{self.name}] Received: {data}")
        return data
"""
    (base_path / "nodes" / "example_node" / "__init__.py").write_text(node_init_content, encoding="utf-8")

    # 5. nodes/example_node/node.toml
    node_toml_content = """[node]
name = "example_node"
description = "An example node"

[build]
base = "python:3.10-slim"
dependencies = []
"""
    (base_path / "nodes" / "example_node" / "node.toml").write_text(node_toml_content, encoding="utf-8")

    # 6. .gitignore
    gitignore_content = """.venv/
.build/
__pycache__/
*.pyc
.env
"""
    (base_path / ".gitignore").write_text(gitignore_content, encoding="utf-8")

    print(f"""
✅ Project '{project_name}' created successfully!

Next steps:
  1. cd {project_name}
  2. uv sync              # Install dependencies
  3. edgeflow deploy main.py --registry localhost:5000
""")


# ==========================================
# 2. Operations (Logs, Dashboard, Doctor)
# ==========================================

def show_logs(node_name: str, namespace: str = "edgeflow", follow: bool = True):
    """
    Wrapper for kubectl logs
    """
    print(f"🔍 Fetching logs for node '{node_name}' in namespace '{namespace}'...")
    
    cmd = [
        "kubectl", "logs", 
        f"-lapp={node_name}",  # Label selector
        "-n", namespace,
        "--all-containers=true",
        "--prefix=true"
    ]
    
    if follow:
        cmd.append("-f")
        
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n👋 Log stream stopped.")
    except FileNotFoundError:
        print("❌ Error: 'kubectl' not found. Please install Kubernetes CLI.")


def open_dashboard(namespace: str = "edgeflow", port: int = 8000):
    """
    Open Gateway Dashboard using kubectl port-forward.
    """
    print(f"🔍 Looking for gateway-svc in namespace '{namespace}'...")
    
    print(f"🔌 Starting port-forward to http://localhost:{port} ...")
    print("Press Ctrl+C to stop.")
    
    cmd = [
        "kubectl", "port-forward",
         f"svc/gateway-svc",
         f"{port}:8000",
         "-n", namespace
    ]
    
    try:
        # Popen을 쓰지 않고 run을 쓰면 블로킹됨 (의도함)
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n👋 Dashboard closed.")
    except Exception as e:
        print(f"❌ Error: {e}")


def check_tool(name: str, install_hint: str) -> bool:
    """Check if a tool is installed and in PATH"""
    path = shutil.which(name)
    if path:
        print(f"✅ {name:<10}: Found ({path})")
        return True
    else:
        print(f"❌ {name:<10}: Not found. {install_hint}")
        return False

def check_k8s_connection():
    """Check connection to Kubernetes cluster"""
    print(f"🔄 {'k8s':<10}: Checking connection...", end="\r")
    try:
        subprocess.run(
            ["kubectl", "get", "nodes"], 
            check=True, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        print(f"✅ {'k8s':<10}: Connected")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"❌ {'k8s':<10}: Connection failed. Check kubeconfig or cluster status.")
        return False

def check_environment():
    """Run full environment check"""
    print("🏥 Running diagnostics for EdgeFlow environment...\n")
    
    all_good = True
    
    # 1. Check Tools
    if not check_tool("uv", "Install via 'pip install uv'"): all_good = False
    if not check_tool("docker", "Install Docker Desktop or Engine"): all_good = False
    if not check_tool("kubectl", "Install kubectl or enable Kubernetes in Docker Desktop"): all_good = False
    if not check_tool("git", "Install Git"): all_good = False

    print("-" * 40)

    # 2. Check Connectivity
    if not check_k8s_connection(): all_good = False

    print("\n" + ("=" * 40))
    if all_good:
        print("✨ Everything looks good! You are ready to deploy.")
    else:
        print("⚠️  Some issues detected. Please fix them before deploying.")


# ==========================================
# 3. Setup (Upgrade)
# ==========================================

def upgrade_framework():
    """
    Upgrade EdgeFlow framework to the latest version using uv.
    """
    print("🔄 Updating EdgeFlow to the latest version...")
    
    # repo_url could be a constant, but hardcoding for now as per request
    cmd = [
        "uv", "tool", "install", "--force",
        "git+https://github.com/seolgugu/edgeflow.git"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("✅ Upgrade complete! Try 'edgeflow --version'")
    except subprocess.CalledProcessError:
        print("❌ Update failed. Please check your internet connection or uv installation.")
    except FileNotFoundError:
        print("❌ Error: 'uv' not found. Please install uv first.")
