# edgeflow/cli/builder.py
"""Per-node container build system"""

import subprocess
import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from .toml_parser import get_build_config


def generate_dockerfile(node_path: str, build_config: Dict[str, Any]) -> str:
    """
    Generate Dockerfile for a specific node folder.
    CRITICAL: Only copies the specific node folder, not the entire project.
    """
    base_image = build_config.get("base", "python:3.10-slim")
    dependencies = build_config.get("dependencies", [])
    system_packages = build_config.get("system_packages", [])
    # [Optimization] Split dependencies into Heavy (Cached) vs Light (Frequent)
    # This prevents re-downloading PyTorch just because we added 'requests'
    known_heavy_libs = {
        "torch", "torchvision", "torchaudio", 
        "tensorflow", "keras", 
        "numpy", "pandas", "scipy", "scikit-learn", 
        "opencv-python", "opencv-python-headless",
        "ultralytics", "pillow", "matplotlib"
    }
    
    heavy_deps = []
    light_deps = []
    
    for dep in dependencies:
        # Check if dep starts with any heavy lib name (e.g. "numpy==1.21")
        dep_name = dep.split("=")[0].split("<")[0].split(">")[0].strip()
        if dep_name in known_heavy_libs:
            heavy_deps.append(dep)
        else:
            light_deps.append(dep)
            
    # Build commands
    heavy_cmd = f"RUN uv pip install --system {' '.join(heavy_deps)}" if heavy_deps else ""
    light_cmd = f"RUN uv pip install --system {' '.join(light_deps)}" if light_deps else ""

    # Build commands
    heavy_cmd = f"RUN uv pip install --system {' '.join(heavy_deps)}" if heavy_deps else None
    light_cmd = f"RUN uv pip install --system {' '.join(light_deps)}" if light_deps else None

    # Always include basic libs + User defined libs
    default_sys_pkgs = ["git", "libgl1", "libglib2.0-0"] # 기본 필수
    
    # [Auto-Fix] PyTorch on ARM64 needs OpenMP (libgomp1)
    if any(lib in str(heavy_deps) for lib in ['torch', 'ultralytics']):
        default_sys_pkgs.append("libgomp1")

    all_sys_pkgs = sorted(list(set(default_sys_pkgs + system_packages)))
    apt_install_cmd = " ".join(all_sys_pkgs)


    
    # Load Template
    from jinja2 import Environment, FileSystemLoader
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("Dockerfile.j2")
    
    dockerfile = template.render(
        base_image=base_image,
        apt_install_cmd=apt_install_cmd,
        node_path=node_path,
        heavy_cmd=heavy_cmd,
        light_cmd=light_cmd
    )

    return dockerfile


def build_node_image(
    project_root: Path,
    node_path: str,
    registry: str,
    project_name: str,
    push: bool = True,
    dry_run: bool = False,
    platforms: str = None
) -> str:
    """
    Build Docker image for a single node.
    
    Args:
        project_root: Root directory of the project
        node_path: Path to node folder (e.g., "nodes/camera")
        registry: Docker registry URL
        project_name: Project name for image tag
        push: Whether to push to registry
        dry_run: If True, only save Dockerfile to .build/
    
    Returns:
        Image tag (e.g., "registry/project-nodes-camera:latest")
    """
    node_dir = project_root / node_path
    if not node_dir.exists():
        raise FileNotFoundError(f"Node folder not found: {node_dir}")
    
    # Parse node.toml
    build_config = get_build_config(node_dir)
    
    # Generate Dockerfile
    dockerfile_content = generate_dockerfile(node_path, build_config)
    
    # Image tag: registry/project-nodes-camera:latest
    node_slug = node_path.replace("/", "-")
    image_tag = f"{registry}/{project_name}-{node_slug}:latest"
    
    if dry_run:
        # Save to .build/ for inspection
        build_dir = project_root / ".build" / "dockerfiles"
        build_dir.mkdir(parents=True, exist_ok=True)
        dockerfile_path = build_dir / f"Dockerfile.{node_slug}"
        dockerfile_path.write_text(dockerfile_content)
        print(f"  📄 [Dry-run] Saved: {dockerfile_path}")
        return image_tag
    
    # Build with temp Dockerfile
    with tempfile.NamedTemporaryFile(
        mode='w', 
        delete=False, 
        prefix=f'Dockerfile.{node_slug}.',
        dir=str(project_root)
    ) as f:
        f.write(dockerfile_content)
        temp_dockerfile = f.name
    
    try:
        # Priority: CLI Argument > node.toml > Default
        target_platforms = "linux/amd64,linux/arm64"
        
        if platforms:
            target_platforms = platforms # CLI override
        elif build_config.get("platforms"):
            target_platforms = ",".join(build_config["platforms"]) # node.toml
            print(f"  🎯 [Config] Using specific platforms: {target_platforms}")

        build_cmd = [
            "docker", "buildx", "build",
            "--platform", target_platforms,
            "-f", temp_dockerfile,
            "-t", image_tag,
        ]
        
        if push:
            build_cmd.append("--push")
        
        build_cmd.append(".")
        
        print(f"  🔨 Building: {image_tag}")
        subprocess.run(build_cmd, check=True, cwd=str(project_root))
        print(f"  ✅ Built: {image_tag}")
        
    finally:
        if os.path.exists(temp_dockerfile):
            os.remove(temp_dockerfile)
    
    return image_tag


def build_all_nodes(
    project_root: Path,
    node_paths: List[str],
    registry: str,
    push: bool = True,
    dry_run: bool = False,
    targets: List[str] = None,
    platforms: str = None
) -> Dict[str, str]:
    """
    Build Docker images for all nodes.
    
    Returns:
        Dict mapping node_path to image_tag
    """
    project_name = project_root.name
    images = {}
    
    print(f"🚀 Building {len(node_paths)} node images...")
    if platforms:
        print(f"  Target Platforms: {platforms}")
    
    for node_path in node_paths:
        # Filter if targets specified
        if targets:
            # Check if any target matches this node path (partial match allowed e.g. 'yolo' matches 'nodes/yolo')
            if not any(t in node_path for t in targets):
                continue

        try:
            image_tag = build_node_image(
                project_root=project_root,
                node_path=node_path,
                registry=registry,
                project_name=project_name,
                push=push,
                dry_run=dry_run,
                platforms=platforms
            )
            images[node_path] = image_tag
        except Exception as e:
            print(f"  ❌ Failed to build {node_path}: {e}")
    
    print(f"✅ Built {len(images)}/{len(node_paths)} images")
    return images


# Legacy function for backward compatibility
def build_and_push(image_tag):
    """Legacy: Build monolithic image (deprecated)"""
    print("⚠️ Warning: build_and_push is deprecated. Use build_all_nodes instead.")
    dockerfile = """
FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . /app
RUN pip install .
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, prefix='Dockerfile.edgeflow.') as f:
        f.write(dockerfile)
        temp_dockerfile_path = f.name

    try:
        subprocess.run([
            "docker", "buildx", "build",
            "--platform", "linux/amd64,linux/arm64",
            "-f", temp_dockerfile_path,
            "-t", image_tag,
            "--push",
            "."
        ], check=True)
    finally:
        if os.path.exists(temp_dockerfile_path):
            os.remove(temp_dockerfile_path)