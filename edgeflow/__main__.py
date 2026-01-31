# edgeflow/__main__.py
import argparse
import sys
from .cli.inspector import inspect_app
from .cli.deployer import deploy_to_k8s, cleanup_namespace
from .cli.manager import (
    add_dependency, show_logs, upgrade_framework, 
    open_dashboard, init_project, check_environment, set_node_architecture
)
from .cli.builder import build_all_nodes

def main():
    parser = argparse.ArgumentParser(description="EdgeFlow CLI v0.2.0")
    subparsers = parser.add_subparsers(dest="command")

    # ==========================
    # 1. BUILD Command (New)
    # ==========================
    build_cmd = subparsers.add_parser("build", help="Build Node Images")
    build_cmd.add_argument("file", help="Path to main.py", nargs="?", default="main.py")
    build_cmd.add_argument("--registry", default="localhost:5000", help="Docker Registry")
    build_cmd.add_argument("--target", "-t", action="append", dest="targets", help="Build specific node only")
    build_cmd.add_argument("--arch", default=None, help="Target architecture (e.g. linux/arm64)")
    build_cmd.add_argument("--push", action="store_true", help="Push after build")

    # ==========================
    # 2. PUSH Command (New)
    # ==========================
    push_cmd = subparsers.add_parser("push", help="Push Node Images")
    push_cmd.add_argument("file", help="Path to main.py", nargs="?", default="main.py")
    push_cmd.add_argument("--registry", default="localhost:5000", help="Docker Registry")
    push_cmd.add_argument("--target", "-t", action="append", dest="targets", help="Push specific node only")

    # ==========================
    # 3. DEPLOY Command (Modified: K8s apply only)
    # ==========================
    deploy = subparsers.add_parser("deploy", help="Deploy manifests to Kubernetes (No Build)")
    deploy.add_argument("file", help="Path to main.py", nargs="?", default="main.py")
    deploy.add_argument("--registry", default="localhost:5000", help="Docker Registry")
    deploy.add_argument("--namespace", default="edgeflow", help="K8s Namespace")
    deploy.add_argument("--dry-run", action="store_true", help="Only generate manifests")
    deploy.add_argument("--target", "-t", action="append", dest="targets", help="Deploy specific node only")

    # ==========================
    # 4. UP Command (New: Build + Push + Deploy)
    # ==========================
    up_cmd = subparsers.add_parser("up", help="Build, Push, and Deploy (All-in-one)")
    up_cmd.add_argument("file", help="Path to main.py", nargs="?", default="main.py")
    up_cmd.add_argument("--registry", default="localhost:5000", help="Docker Registry")
    up_cmd.add_argument("--namespace", default="edgeflow", help="K8s Namespace")
    up_cmd.add_argument("--target", "-t", action="append", dest="targets", help="Target specific node only")
    up_cmd.add_argument("--arch", default=None, help="Target architecture")
    up_cmd.add_argument("--push", action="store_true", default=True, help="Push after build (default: True)")
    up_cmd.add_argument("--dry-run", action="store_true", help="Only generate manifests")


    # [Other Commands same as before...]
    clean = subparsers.add_parser("clean", help="Clean up namespace resources")
    clean.add_argument("--namespace", "-n", default="edgeflow", help="K8s Namespace")

    add = subparsers.add_parser("add", help="Add dependency to node.toml")
    add.add_argument("package", help="Package Name")
    add.add_argument("--node", help="Path to node folder")
    add.add_argument("--apt", action="store_true", help="Add as system package")

    logs = subparsers.add_parser("logs", help="View node logs from K8s")
    logs.add_argument("node", help="Node Name")
    logs.add_argument("--namespace", "-n", default="edgeflow", help="K8s Namespace")

    init_cmd = subparsers.add_parser("init", help="Initialize a new project")
    init_cmd.add_argument("name", help="Project Name")

    subparsers.add_parser("doctor", help="Check environment health")

    dash = subparsers.add_parser("dashboard", help="Open Gateway Dashboard")
    dash.add_argument("--port", "-p", type=int, default=8000, help="Local port")
    dash.add_argument("--namespace", "-n", default="edgeflow", help="K8s Namespace")

    subparsers.add_parser("upgrade", help="Upgrade EdgeFlow to latest version")

    local_cmd = subparsers.add_parser("local", help="Run locally with uv")
    local_cmd.add_argument("file", nargs="?", default="main.py", help="Path to main.py")

    set_arch = subparsers.add_parser("set-arch", help="Set target architecture for a node")
    set_arch.add_argument("node", help="Path to node folder")
    set_arch.add_argument("arch", help="Target architecture")

    # ==========================
    # 11. SYNC Command (New)
    # ==========================
    sync_cmd = subparsers.add_parser("sync", help="Sync changed files to running pods (Dev Mode)")
    sync_cmd.add_argument("file", nargs="?", default="main.py", help="Path to main.py")
    sync_cmd.add_argument("--namespace", "-n", default="edgeflow", help="K8s Namespace")
    sync_cmd.add_argument("--target", "-t", action="append", dest="targets", help="Sync specific node only")

    args = parser.parse_args()

    # Dispatch
    if args.command == "build":
        _handle_build(args)
    elif args.command == "push":
        # Push is essentially build with push=True but reusing cache
        args.push = True
        _handle_build(args)
    elif args.command == "deploy":
        _handle_deploy_only(args)
    elif args.command == "up":
        _handle_up(args)
    elif args.command == "sync":
        _handle_sync(args)
    elif args.command == "clean":
        cleanup_namespace(args.namespace)
    elif args.command == "add":
        add_dependency(args.package, args.node, is_apt=args.apt)
    elif args.command == "logs":
        show_logs(args.node, args.namespace)
    elif args.command == "init":
        init_project(args.name)
    elif args.command == "doctor":
        check_environment()
    elif args.command == "dashboard":
        open_dashboard(args.namespace, args.port)
    elif args.command == "upgrade":
        upgrade_framework()
    elif args.command == "local":
        from .cli.runner import run_local
        run_local(args.file)
    elif args.command == "set-arch":
        set_node_architecture(args.node, args.arch)
    else:
        parser.print_help()


def _load_system(file_path):
    try:
        return inspect_app(file_path)
    except Exception as e:
        print(f"❌ Error loading app: {e}")
        sys.exit(1)

def _handle_build(args):
    system = _load_system(args.file)
    print(f"🔨 Building System: {system.name}")
    from pathlib import Path
    
    node_paths = [spec.path for spec in system.specs.values()]
    
    # If build command, push defaults to False unless flag set
    # If push command, args.push is already True
    
    build_all_nodes(
        project_root=Path(args.file).resolve().parent,
        node_paths=node_paths,
        registry=args.registry,
        push=args.push,
        targets=args.targets,
        platforms=args.arch
    )

def _handle_deploy_only(args):
    system = _load_system(args.file)
    project_root = Path(args.file).resolve().parent
    print(f"🚀 Deploying System (Manifests only): {system.name}")
    deploy_to_k8s(
        system=system,
        registry=args.registry,
        namespace=args.namespace,
        build=False, # Skip build
        push=False,
        dry_run=args.dry_run,
        targets=args.targets,
        project_root=project_root
    )

def _handle_up(args):
    system = _load_system(args.file)
    project_root = Path(args.file).resolve().parent
    print(f"🚀 UP: Building, Pushing, and Deploying {system.name}")
    
    # 1. Build & Push
    from pathlib import Path
    node_paths = [spec.path for spec in system.specs.values()]
    
    build_all_nodes(
        project_root=project_root,
        node_paths=node_paths,
        registry=args.registry,
        push=True, # Always push in UP mode
        targets=args.targets,
        platforms=args.arch
    )
    
    # 2. Deploy
    deploy_to_k8s(
        system=system,
        registry=args.registry,
        namespace=args.namespace,
        build=False, # Already built
        push=False,
        dry_run=args.dry_run,
        targets=args.targets,
        project_root=project_root
    )

def _handle_sync(args):
    from .cli.syncer import sync_nodes
    from pathlib import Path
    
    system = _load_system(args.file)
    project_root = Path(args.file).resolve().parent
    node_paths = [spec.path for spec in system.specs.values()]
    
    sync_nodes(
        project_root=project_root,
        node_paths=node_paths,
        namespace=args.namespace,
        targets=args.targets
    )


if __name__ == "__main__":
    main()