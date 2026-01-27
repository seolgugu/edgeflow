import os
from pathlib import Path

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
