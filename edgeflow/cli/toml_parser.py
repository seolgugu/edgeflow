# edgeflow/cli/toml_parser.py
"""Parser for node.toml build configuration files"""

from pathlib import Path
from typing import Dict, Any

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for older Python


def parse_node_toml(toml_path: Path) -> Dict[str, Any]:
    """
    Parse node.toml file for build configuration.
    
    Expected format:
    ```toml
    [build]
    base = "python:3.10-slim"
    dependencies = ["opencv-python", "numpy"]
    
    [runtime]
    gpu = true
    ```
    
    Returns default config if file doesn't exist.
    """
    default_config = {
        "build": {
            "base": "python:3.10-slim",
            "dependencies": []
        },
        "runtime": {}
    }
    
    if not toml_path.exists():
        return default_config
    
    with open(toml_path, "rb") as f:
        return tomllib.load(f)


def get_build_config(node_path: Path) -> Dict[str, Any]:
    """Get build configuration for a node folder"""
    toml_file = node_path / "node.toml"
    config = parse_node_toml(toml_file)
    
    # Flatten for easy access
    # Flatten for easy access
    build_section = config.get("build", {})
    return {
        "base": build_section.get("base", "python:3.10-slim"),
        "dependencies": build_section.get("dependencies", []),
        "system_packages": build_section.get("system_packages", []),
        "platforms": build_section.get("platforms", []), # e.g. ["linux/arm64"]
        "gpu": config.get("runtime", {}).get("gpu", False)
    }
