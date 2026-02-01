# examples/yolo/main.py
import sys
from edgeflow import System, QoS
from edgeflow.comms import RedisListBroker  # List-based broker for better performance

# ============================================================
# 1. 전역 범위(Global Scope)에서 시스템 정의
# CLI 도구는 이 'app' 변수를 찾습니다.
# ============================================================
broker = RedisListBroker() 
app = System("yolo-app", broker=broker)  # 변수명을 'app'으로 하면 더 확실합니다.

# 2. Register Nodes
cam = app.node("nodes/camera")
yolo = app.node("nodes/yolov5", replicas=1)
gw = app.node("nodes/gateway", node_port=30080)

# 3. Wiring
# Camera -> YoloV5 (Realtime)
app.link(cam).to(yolo, qos=QoS.REALTIME)

# Camera -> Gateway (Debugging)
app.link(cam).to(gw)

# YoloV5 -> Gateway (Result)
app.link(yolo).to(gw)

# ============================================================
# 실행 진입점
# ============================================================
if __name__ == "__main__":
    print("🚀 System Ready. Run with 'edgeflow deploy' or 'python main.py'")
    # 직접 실행할 때만 run() 호출
    app.run()