# edgeflow/__main__.py
import argparse
import sys
from .cli.inspector import inspect_app
from .cli.deployer import deploy_to_k8s

def main():
    parser = argparse.ArgumentParser(description="EdgeFlow CLI v0.2.0")
    subparsers = parser.add_subparsers(dest="command")

    # deploy 명령어
    deploy = subparsers.add_parser("deploy")
    deploy.add_argument("file", help="Path to main.py")
    deploy.add_argument("--registry", default="localhost:5000", help="Docker Registry")
    deploy.add_argument("--namespace", default="edgeflow", help="K8s Namespace")
    deploy.add_argument("--dry-run", action="store_true", help="Only generate manifests, don't apply")
    deploy.add_argument("--no-build", action="store_false", dest="build", help="Skip building images")
    deploy.set_defaults(build=True)

    args = parser.parse_args()

    if args.command == "deploy":
        print(f"🔍 Inspecting {args.file}...")
        try:
            system = inspect_app(args.file)
        except Exception as e:
            print(f"❌ Error loading app: {e}")
            sys.exit(1)
        
        print(f"🚀 Deploying System: {system.name} (Namespace: {args.namespace})")
        
        try:
            deploy_to_k8s(
                system=system,
                registry=args.registry,
                namespace=args.namespace,
                build=args.build,
                push=args.build,  # Push if built
                dry_run=args.dry_run
            )
            
            if args.dry_run:
                print("✅ Dry-run complete. Manifests saved in .build/ manifests")
            else:
                print("✅ Deployment complete!")
                
        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()