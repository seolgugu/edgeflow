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

def add_dependency(package: str, node_path: str = None, is_apt: bool = False):
    """
    Add a package (python or apt) to node.toml.
    """
    target_file = None
    
    # 1. 경로 자동 추론
    if node_path:
        path = Path(node_path)
        if path.is_file() and path.name == "node.toml":
            target_file = path
        elif path.is_dir():
            target_file = path / "node.toml"
    else:
        cwd = Path.cwd()
        if (cwd / "node.toml").exists():
            target_file = cwd / "node.toml"
    
    if not target_file or not target_file.exists():
        print(f"❌ Error: Could not find node.toml in '{node_path or 'current directory'}'")
        sys.exit(1)

    # 2. 파일 읽기
    content = target_file.read_text(encoding="utf-8")
    
    # 3. 키 이름 결정 (dependencies vs system_packages)
    key_name = "system_packages" if is_apt else "dependencies"
    
    # 4. Regex로 키 찾기
    # 예: dependencies = [...] 또는 system_packages = [...]
    pattern = rf'({key_name}\s*=\s*\[)(.*?)(\])'
    
    match = re.search(pattern, content, re.DOTALL)
    if match:
        prefix, current_deps, suffix = match.groups()
        
        # 중복 확인
        if f'"{package}"' in current_deps or f"'{package}'" in current_deps:
            print(f"⚠️ Package '{package}' is already in {key_name}")
            return

        # 추가
        clean_deps = current_deps.strip()
        new_dep = f', "{package}"' if clean_deps and not clean_deps.endswith(',') else f'"{package}"'
        if not clean_deps:
            new_dep = f'"{package}"'
            
        new_content = content.replace(
            match.group(0), 
            f'{prefix}{current_deps}{new_dep}{suffix}'
        )
    else:
        # 키가 없으면 [build] 섹션 끝에 추가
        if is_apt:
            # [build] 섹션을 찾아 그 아래에 system_packages 추가
            build_match = re.search(r'(\[build\]\s*)(.*?)(\n\[|\Z)', content, re.DOTALL)
            if build_match:
                # [build] 섹션이 있으면 그 안에 추가
                new_entry = f'\nsystem_packages = ["{package}"]'
                # [build] ... (내용) ... [다음섹션] -> [build] ... (내용) new_entry [다음섹션]
                # 이게 복잡하므로 단순하게 dependencies 줄을 찾아서 그 뒤에 추가하는 게 안전
                dep_match = re.search(r'(dependencies\s*=\s*\[.*?\])', content, re.DOTALL)
                if dep_match:
                    new_content = content.replace(
                        dep_match.group(1),
                        f'{dep_match.group(1)}\n{key_name} = ["{package}"]'
                    )
                else:
                    # dependencies도 없으면 [build] 바로 뒤에
                     new_content = content.replace("[build]", f'[build]\n{key_name} = ["{package}"]')
            else:
                print(f"❌ Error: [build] section not found.")
                return
        else:
             print(f"❌ Error: '{key_name} = []' list not found.")
             sys.exit(1)

    # 5. 저장
    target_file.write_text(new_content, encoding="utf-8")
    type_label = "System Package" if is_apt else "Python Package"
    print(f"✅ Added {type_label} '{package}' to {target_file}")


def set_node_architecture(node_path: str, arch: str):
    """
    Set build architecture for a node in node.toml.
    """
    # 1. 파일 찾기
    path = Path(node_path)
    if path.is_file() and path.name == "node.toml":
        target_file = path
    elif path.is_dir():
        target_file = path / "node.toml"
    else:
        # try relative to cwd
        target_file = Path.cwd() / "node.toml"
        if not target_file.exists():
            target_file = Path.cwd() / node_path / "node.toml"

    if not target_file.exists():
        print(f"❌ Error: Could not find node.toml in '{node_path}'")
        return

    # 2. 파일 읽기
    content = target_file.read_text(encoding="utf-8")
    
    # 3. 플랫폼 설정
    # platforms = ["linux/arm64"] 형태로 변환
    new_platforms_str = f'platforms = ["{arch}"]'
    
    # 4. Regex로 기존 platforms 찾기
    pattern = r'(platforms\s*=\s*\[.*?\])'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        # 기존 값 교체
        new_content = content.replace(match.group(1), new_platforms_str)
        print(f"♻️ Updated architecture to {arch}")
    else:
        # 키가 없으면 [build] 섹션 끝에 추가
        build_match = re.search(r'(\[build\]\s*)(.*?)(\n\[|\Z)', content, re.DOTALL)
        if build_match:
            # [build] 섹션 안에 추가
            # dependencies 라인을 찾아서 그 뒤에 추가하는 게 안전
            dep_match = re.search(r'(dependencies\s*=\s*\[.*?\])', content, re.DOTALL)
            if dep_match:
                new_content = content.replace(
                    dep_match.group(1),
                    f'{dep_match.group(1)}\n{new_platforms_str}'
                )
            else:
                # dependencies가 없으면 [build] 바로 뒤에
                new_content = content.replace("[build]", f'[build]\n{new_platforms_str}')
            print(f"✅ Set architecture to {arch}")
        else:
            print(f"❌ Error: [build] section not found in node.toml")
            return

    # 5. 저장
    target_file.write_text(new_content, encoding="utf-8")



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
        "git+https://github.com/witdory/edgeflow.git"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("✅ Upgrade complete! Try 'edgeflow --version'")
    except subprocess.CalledProcessError:
        print("❌ Update failed. Please check your internet connection or uv installation.")
    except FileNotFoundError:
        print("❌ Error: 'uv' not found. Please install uv first.")
