import shutil
import subprocess
import sys

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
