# edgeflow/cli/syncer.py
"""
Smart Sync: Code synchronization for rapid development
Copies local source code to running pods without full image rebuilds.
"""

import os
import subprocess
from pathlib import Path
from typing import List
from kubernetes import client, config

def get_pod_names(namespace: str, label_selector: str) -> List[str]:
    """Get list of running pod names matching label"""
    try:
        config.load_kube_config()
    except Exception:
        # Fallback to K3s config
        k3s_config = "/etc/rancher/k3s/k3s.yaml"
        if os.path.exists(k3s_config):
            config.load_kube_config(config_file=k3s_config)
            
    v1 = client.CoreV1Api()
    try:
        pods = v1.list_namespaced_pod(
            namespace=namespace, 
            label_selector=label_selector
        )
        # Filter only running pods
        return [
            p.metadata.name 
            for p in pods.items 
            if p.status.phase == "Running"
        ]
    except Exception as e:
        print(f"⚠️ Error listing pods: {e}")
        return []


def sync_nodes(
    project_root: Path,
    node_paths: List[str],
    namespace: str = "edgeflow",
    targets: List[str] = None
):
    """
    Sync source code from local to running pods.
    """
    print(f"🔄 Syncing code to running pods in namespace '{namespace}'...")
    
    synced_count = 0
    
    for node_path in node_paths:
        # 1. Filter targets
        if targets:
            if not any(t in node_path for t in targets):
                continue
                
        # 2. Identify Node Name (from path 'nodes/camera' -> 'camera')
        # This MUST match the logic in deployer.py (name=...)
        # We assume the user defined name matches the folder name or we need the system spec.
        # But here we only have paths. Let's try to infer or use label approach.
        # deployer.py uses: app={{ name }}
        # Inspector returns spec.name. We should probably pass spec, but for now let's use the folder name default
        # or we scan main.py again? The caller passes node_paths.
        
        # Improvement: caller should pass {name: path} dict.
        # For now, let's assume standard 'nodes/<name>' structure.
        node_name = Path(node_path).name 
        
        # 3. Find Pods
        label = f"app={node_name}"
        pods = get_pod_names(namespace, label)
        
        if not pods:
            # Maybe the name is 'yolo-app-nodes-camera'? 
            # Let's try flexible search later, but for now exact match 'app=name' 
            # defined in deployment.yaml.j2
            print(f"  ⚠️ No running pods found for '{node_name}' (label: {label})")
            continue
            
        # 4. Sync Files
        local_src = project_root / node_path
        remote_dest = f"/app/{node_path}" # e.g. /app/nodes/camera
        
        for pod in pods:
            print(f"  ⚡ Syncing {node_path} -> {pod}:{remote_dest}")
            
            try:
                # Sync each .py file individually using kubectl exec
                for py_file in local_src.glob("*.py"):
                    file_content = py_file.read_text(encoding="utf-8")
                    remote_file = f"{remote_dest}/{py_file.name}"
                    
                    # Use kubectl exec with echo to write file content
                    # Escape for shell
                    escaped_content = file_content.replace("'", "'\"'\"'")
                    
                    write_cmd = [
                        "kubectl", "exec", pod, "-n", namespace, "--",
                        "sh", "-c", f"cat > {remote_file} << 'EOFMARKER'\n{file_content}\nEOFMARKER"
                    ]
                    
                    result = subprocess.run(write_cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        print(f"     ⚠️ Failed to sync {py_file.name}: {result.stderr}")
                    else:
                        print(f"     ✓ {py_file.name}")
                
                synced_count += 1
                
                # Trigger Reload (Send SIGHUP to PID 1)
                reload_cmd = ["kubectl", "exec", pod, "-n", namespace, "--", "kill", "-HUP", "1"]
                subprocess.run(reload_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                print(f"     ✅ Synced & Reloaded.")
                
            except subprocess.CalledProcessError as e:
                print(f"     ❌ Sync failed: {e}")

    if synced_count > 0:
        print(f"\n✨ Synced to {synced_count} pods. Changes applied immediately (if auto-reload is on).")
        print(f"💡 Hint: If code is not updating, try 'kubectl delete pod <pod-name>' to force restart.")
    else:
        print("\n⚠️ No pods synced. Are the pods running?")
