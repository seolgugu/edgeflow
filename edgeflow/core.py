#edgeflow/core.py
import sys
import argparse
import time
import threading
import importlib
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from .handlers import RedisHandler, TcpHandler
from .config import settings
from .registry import NodeSpec, NodeRegistry
from .qos import QoS


class Linker:
    def __init__(self, system: 'System', source: NodeSpec):
        self.system = system
        self.source = source

    def to(self, target: NodeSpec, channel: str = None, qos: QoS = QoS.REALTIME) -> 'Linker':
        """Register a connection between nodes with QoS policy"""
        # 1. Output (Source -> Target)
        if 'targets' not in self.source.config:
            self.source.config['targets'] = []
            
        # Determine Protocol
        protocol = 'redis'
        if target.config.get('type') == 'gateway' or channel is not None:
            protocol = 'tcp'

        self.source.config['targets'].append({
            'name': target.name,
            'protocol': protocol,
            'channel': channel,
            'qos': qos
        })
        
        # 2. Input (Target <- Source)
        if 'sources' not in target.config:
            target.config['sources'] = []
            
        target.config['sources'].append({
            'name': self.source.name,
            'qos': qos
        })
        
        return Linker(self.system, target)


class System:
    """
    Infrastructure Definition (Blueprint Pattern)
    - Lazy loading: node() does NOT import classes
    - Wiring: link() stores metadata only
    - Execution: run() loads classes and executes
    """
    def __init__(self, name: str, broker):
        self.name = name
        self.broker = broker
        self.specs: Dict[str, NodeSpec] = {}

    @staticmethod
    def _inspect_node_type(path: str) -> str:
        """Inspect the node class to determine its type (without instantiating)"""
        try:
            module_path = path.replace("/", ".")
            module = importlib.import_module(module_path)
            
            # Find EdgeNode subclass
            from .nodes import EdgeNode, ProducerNode, ConsumerNode, GatewayNode, FusionNode, SinkNode
            base_classes = {EdgeNode, ProducerNode, ConsumerNode, GatewayNode, FusionNode, SinkNode}
            
            for obj in vars(module).values():
                if isinstance(obj, type) and issubclass(obj, EdgeNode):
                    if obj in base_classes: continue
                    if obj.__module__ == module.__name__:
                        return getattr(obj, "node_type", "generic")
        except Exception as e:
            print(f"⚠️ Failed to inspect node type for {path}: {e}")
        return "generic"

    def node(self, path: str, **kwargs) -> NodeSpec:
        """Register node by path (uses global registry for sharing)"""
        spec = NodeRegistry.get_or_create(path, **kwargs)
        
        # Auto-detect node type if not provided
        if 'type' not in spec.config:
            spec.config['type'] = self._inspect_node_type(path)
            
        self.specs[spec.name] = spec
        return spec

    def share(self, spec: NodeSpec) -> NodeSpec:
        """Import a node from another System (add to my scope)"""
        self.specs[spec.name] = spec
        return spec

    def link(self, source: NodeSpec) -> Linker:
        """Create connection builder for wiring nodes"""
        return Linker(self, source)

    # Removed _load_node_class and _instantiate_nodes as they are no longer used.
    # Node instantiation happens in separate processes via _run_node_process.

    def run(self):
        """
        Start the System execution (blocking)
        - Proxy to the top-level run() function
        """
        run(self)

    @staticmethod
    def _run_node_process(name: str, path: str, node_config: Dict, broker_config: Dict):
        """Bootstrap function running in a separate process"""
        # 1. Re-establish Broker Connection using the serialization protocol
        # Dynamic import based on broker_config
        module_path, class_name = broker_config['__class_path__'].rsplit('.', 1)
        module = importlib.import_module(module_path)
        BrokerClass = getattr(module, class_name)
        
        # Use the from_config protocol method
        broker = BrokerClass.from_config(broker_config)
        print(f"⚡ [Process:{name}] Broker connected: {broker_config.get('host')} ({class_name})", flush=True)

        # 2. Load Class & Instantiate
        # We need to replicate _load_node_class logic or import it.
        # Since this is static, we can't call self._load_node_class easily unless we duplicate logic 
        # or make _load_node_class static.
        # For simplicity, we'll re-implement import logic here or make _load static.
        
        # 2. Load Class & Instantiate
        import os
        os.environ["NODE_NAME"] = name

        try:
            module_path = path.replace("/", ".")
            module = importlib.import_module(module_path)
            
            # Find class
            from .nodes import EdgeNode, ProducerNode, ConsumerNode, GatewayNode, FusionNode, SinkNode
            base_classes = {EdgeNode, ProducerNode, ConsumerNode, GatewayNode, FusionNode, SinkNode}
            
            node_cls = None
            for obj_name, obj in vars(module).items():
                if isinstance(obj, type) and issubclass(obj, EdgeNode):
                    if obj in base_classes: continue
                    if obj.__module__ == module.__name__:
                        node_cls = obj
                        break
            
            if not node_cls:
                raise ImportError(f"No EdgeNode subclass found in {path}")
                
            node = node_cls(broker=broker, **node_config)
            
        except Exception as e:
            print(f"⚠️ [Process:{name}] Failed to load node: {e}", flush=True)
            print(f"🔄 [Process:{name}] Falling back to FrameworkErrorNode...", flush=True)
            
            # Fallback to FrameworkErrorNode
            from .nodes.producer import FrameworkErrorNode
            node = FrameworkErrorNode(broker=broker, error_msg=f"{type(e).__name__}: {e}", **node_config)
        
        # 3. Execute
        print(f"🚀 [Process:{name}] Starting execution loop...", flush=True)
        node.execute()

# Backward compatibility alias
EdgeApp = System


def run(*systems: System):
    """
    Run one or multiple Systems (Entry Point)
    
    - Single System: run(sys)
    - Multi System:  run(sys1, sys2)
    """
    import multiprocessing
    
    # 1. Collect all unique nodes
    all_specs: Dict[str, NodeSpec] = {}
    for s in systems:
        for name, spec in s.specs.items():
            all_specs[name] = spec
    
    # 2. Launch processes (Wiring is already in spec.config)
    processes = []
    
    # [Reset Broker State]
    if systems and hasattr(systems[0].broker, 'reset'):
         systems[0].broker.reset()

    default_broker_config = systems[0].broker.to_config()
    
    for name, spec in all_specs.items():
        p = multiprocessing.Process(
            target=System._run_node_process,
            args=(name, spec.path, spec.config, default_broker_config),
            daemon=True
        )
        p.start()
        processes.append(p)
    
    print(f"▶️ [EdgeFlow] Launching {len(processes)} nodes from {len(systems)} system(s)")
    
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n👋 System Shutdown - Stopping all processes...")
        for p in processes:
            p.terminate()
        import sys as sys_module
        sys_module.exit(0)