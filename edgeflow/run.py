import sys
import os
import signal
import time
import multiprocessing
import importlib
import inspect
from edgeflow.nodes import EdgeNode

# =========================================================
# Node Runner Logic (Worker Process)
# =========================================================
def _start_node_process(module_name):
    """
    Actual logic to load and run the node.
    This runs in a separate process.
    """
    # 1. Import module
    try:
        # In hot-reload, we might need to invalidate caches if we were in the same process,
        # but since we are a fresh process, importlib.import_module is fine.
        mod = importlib.import_module(module_name)
    except Exception as e:
        print(f"❌ [Loader] Failed to load module '{module_name}': {e}")
        from edgeflow.nodes.producer import FrameworkErrorNode
        node = FrameworkErrorNode(error_msg=f"Load Fail: {e}")
        node.execute()
        return

    # 2. Find EdgeNode subclass
    node_class = None
    for name, obj in inspect.getmembers(mod):
        if inspect.isclass(obj) and issubclass(obj, EdgeNode) and obj is not EdgeNode:
            if obj.__module__ == mod.__name__:
                node_class = obj
                break
    
    if not node_class:
        print(f"❌ No EdgeNode subclass found in '{module_name}'")
        from edgeflow.nodes.producer import FrameworkErrorNode
        node = FrameworkErrorNode(error_msg=f"No Node Class in {module_name}")
        node.execute()
        return

    # 3. Instantiate and Run
    print(f"🚀 [Worker] Running Node: {node_class.__name__} (PID: {os.getpid()})")
    
    try:
        node = node_class()
        node.execute()
    except Exception as e:
        print(f"❌ [Worker] Node Execution Failed: {e}")
        import traceback
        traceback.print_exc()

# =========================================================
# Supervisor Logic (Main Process)
# =========================================================
class NodeSupervisor:
    def __init__(self, module_name):
        self.module_name = module_name
        self.process = None
        self.running = True

    def start(self):
        # Register Signal Handlers
        signal.signal(signal.SIGHUP, self.handle_reload)
        signal.signal(signal.SIGTERM, self.handle_exit)
        signal.signal(signal.SIGINT, self.handle_exit)

        print(f"👀 [Supervisor] Started. Watching for SIGHUP to reload. (PID: {os.getpid()})")
        
        while self.running:
            self.spawn_worker()
            
            # Wait for child to exit
            while self.process and self.process.is_alive():
                time.sleep(1)
            
            if self.running:
                print("⚠️ [Supervisor] Worker exited unexpectedly. Restarting in 3s...")
                time.sleep(3)

    def spawn_worker(self):
        if self.process and self.process.is_alive():
            return
            
        print(f"🔄 [Supervisor] Spawning worker for '{self.module_name}'...")
        self.process = multiprocessing.Process(
            target=_start_node_process, 
            args=(self.module_name,),
            daemon=True
        )
        self.process.start()

    def handle_reload(self, signum, frame):
        print(f"\n♻️ [Supervisor] SIGHUP received! Reloading node...")
        if self.process and self.process.is_alive():
            print("   Killing old worker...")
            self.process.terminate()
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.kill()
        
        # Loop in start() will automatically respawn

    def handle_exit(self, signum, frame):
        print(f"\n🛑 [Supervisor] Stopping...")
        self.running = False
        if self.process and self.process.is_alive():
            self.process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m edgeflow.run <module_path>")
        sys.exit(1)
    
    # Add /app to sys.path
    sys.path.append("/app")
    
    module_path = sys.argv[1]
    
    # Run Supervisor
    supervisor = NodeSupervisor(module_path)
    supervisor.start()
