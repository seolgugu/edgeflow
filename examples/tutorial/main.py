# examples/my-robot/main_multi.py
"""
Multi-System Example - Realtime + Logging with QoS
"""

from edgeflow import System, QoS, run
from edgeflow.comms import RedisListBroker  # List-based broker for better performance

# ============================================================
# System 1: Realtime Pipeline (Redis)
# ============================================================
app = System("realtime", broker=RedisListBroker())

cam = app.node("nodes/camera", device="camera", fps=30)
gpu = app.node("nodes/yolo", device="gpu", replicas=2)
gw  = app.node("nodes/gateway", node_port=30080)

app.link(cam).to(gpu, qos=QoS.REALTIME).to(gw)  # GPU: 최신만 (실시간)
app.link(cam).to(gw)                             # Raw -> Gateway (TCP)

# ============================================================
# Run System
# ============================================================
if __name__ == "__main__":
    print("🚧 Building Multi-System Pipeline...")
    print(f"\n✅ System Ready!")
    print(f" - Realtime: camera -> yolo (QoS.REALTIME) -> gateway")
    print("\n🚀 Starting EdgeFlow (Multi-System)...")
    
    app.run()
    #run(sys) #if using multi Systems
