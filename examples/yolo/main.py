# examples/yolo/main.py
import sys
from edgeflow import System, QoS

# [Fix] Import Gateway for wiring, but we use "nodes/gateway" path in node()
# from edgeflow.nodes import GatewayNode 

def main():
    # 1. Define System
    # - Port 6379: Control Plane (Stream)
    # - Port 6380: Data Plane (Blob)
    from edgeflow.comms import DualRedisBroker
    broker = DualRedisBroker() 
    
    sys = System("yolo-app", broker=broker)

    # 2. Register Nodes
    # - Camera: Produces frames (CPU)
    # - YoloV5: Consumes frames, detects objects (CPU/GPU)
    # - Gateway: Web Dashboard
    
    cam = sys.node("nodes/camera")
    yolo = sys.node("nodes/yolov5", replicas=1)
    
    # Use standard gateway from existing example or core? 
    # Since we are in examples/yolo, we don't have a local gateway folder unless we copy it.
    # We can use the one from 'my-robot' via absolute path or just copy it.
    # For simplicity, let's assume we want a gateway. 
    # We can point to the standard gateway in my-robot for now or create a minimal one.
    # Let's create a minimal gateway in nodes/gateway to be self-contained.
    gw = sys.node("nodes/gateway", node_port=30080)

    # 3. Wiring
    # Camera -> YoloV5 (Realtime)
    sys.link(cam).to(yolo, qos=QoS.REALTIME)
    
    # Camera -> Gateway (For debugging input)
    sys.link(cam).to(gw)
    
    # YoloV5 -> Gateway (For viewing result)
    sys.link(yolo).to(gw)

    print("🚀 System Ready. Run with 'edgeflow deploy' or 'python main.py'")
    sys.run()

if __name__ == "__main__":
    main()
