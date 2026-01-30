import sys
import importlib
import inspect
import os
from edgeflow.nodes import EdgeNode

def run_node(module_name):
    # 1. Import module
    # 1. Import module
    try:
        mod = importlib.import_module(module_name)
    except Exception as e:
        print(f"❌ [Loader] Failed to load module '{module_name}': {e}")
        
        # [Fix] Instead of crashing, run FrameworkErrorNode to broadcast error
        from edgeflow.nodes.producer import FrameworkErrorNode
        print(f"⚠️ [Loader] Fallback to FrameworkErrorNode")
        node = FrameworkErrorNode(error_msg=f"Load Fail: {e}")
        node.execute()
        return

    # 2. Find EdgeNode subclass
    node_class = None
    for name, obj in inspect.getmembers(mod):
        if inspect.isclass(obj) and issubclass(obj, EdgeNode) and obj is not EdgeNode:
            # Only pick class defined in this module
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
    print(f"🚀 Running Node: {node_class.__name__}")
    
    # Note: EdgeNode.__init__ will create default RedisBroker if broker is None.
    try:
        node = node_class()
        node.execute()
    except Exception as e:
        print(f"❌ Node Execution Failed: {e}")
        import traceback
        traceback.print_exc()
        # Even runtime init error -> Error Node
        from edgeflow.nodes.producer import FrameworkErrorNode
        node = FrameworkErrorNode(error_msg=f"Init Error: {e}")
        node.execute()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m edgeflow.run <module_path>")
        sys.exit(1)
    
    # Add /app to sys.path to find nodes package
    sys.path.append("/app")
    
    run_node(sys.argv[1])
