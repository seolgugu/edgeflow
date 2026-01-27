from edgeflow import System, QoS
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
