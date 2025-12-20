import time
import numpy as np
import cv2
from edgeflow import EdgeApp

# 앱 초기화 (k3s 환경에서 실행된다고 가정)
app = EdgeApp("delivery-robot-v2")

# ==========================================
# 1. Producers (데이터 생성)
# - 핵심: timestamp를 반드시 찍어서 보내야 동기화가 됨
# ==========================================

@app.producer(topic="cam_front", fps=30)
def camera_driver():
    """전방 카메라 드라이버 시뮬레이션"""
    # 실제로는 cap.read() 겠지만 여기선 더미 데이터
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    
    return {
        "data": frame, 
        "timestamp": time.time(), # [중요] 캡처 시점 시간 (Sync 기준)
        "seq": 0
    }

@app.producer(topic="lidar_top", fps=10) # LiDAR는 보통 10Hz
def lidar_driver():
    """상단 LiDAR 드라이버 시뮬레이션"""
    # (x, y, z, intensity) 포인트 클라우드 데이터
    points = np.random.rand(1000, 4).astype(np.float32)
    
    return {
        "data": points,
        "timestamp": time.time(), # [중요] 캡처 시점 시간
        "seq": 0
    }


# ==========================================
# 2. Sensor Fusion Consumer (클래스형)
# - 무거운 AI 모델 로딩 필요 -> 클래스 사용
# - 두 센서의 시간이 맞아야 함 -> @app.sync 사용
# ==========================================

@app.sync(sources=["cam_front", "lidar_top"], tolerance=0.05, replicas=2)
class SensorFusionNode:
    def setup(self):
        """[초기화] 프로세스 시작 시 1회 실행 (캘리브레이션/모델 로드)"""
        print("⚡ [Fusion] Loading YOLOv8 & Calibration Matrix...")
        
        # 1. 무거운 AI 모델 로드 (GPU)
        # self.model = YOLO('yolov8x.pt')
        self.model_name = "YOLOv8-X"
        
        # 2. 캘리브레이션 매트릭스 로드 (Camera <-> LiDAR 변환 행렬)
        self.calib_matrix = np.eye(4) 
        print("✅ [Fusion] Setup Complete.")

    def process(self, cam_front, lidar_top):
        """
        [동기화 실행]
        프레임워크가 타임스탬프 오차 0.05s(50ms) 이내인 
        카메라와 라이다 데이터를 짝지어서 줍니다.
        """
        img = cam_front["data"]
        pcl = lidar_top["data"]
        ts_diff = abs(cam_front["timestamp"] - lidar_top["timestamp"])

        # 1. 이미지에서 객체 탐지 (YOLO)
        # boxes = self.model(img)
        detected_objects = [{"class": "person", "bbox": [100, 100, 200, 300]}]

        # 2. 퓨전 (이미지 BBox 안에 들어오는 LiDAR 포인트의 거리 계산)
        # dist = project_lidar_to_image(pcl, boxes, self.calib_matrix)
        estimated_dist = 3.5  # 3.5m 앞에 사람 있음

        # 3. 결과 패키징
        result = {
            "obstacle": "person",
            "distance": estimated_dist,
            "fusion_latency": ts_diff, # 싱크 오차 기록
            "timestamp": cam_front["timestamp"] # 원본 시간 유지
        }
        
        # 리턴하면 자동으로 'fusion_result' 토픽(함수이름)으로 발행됨
        return result


# ==========================================
# 3. Logger Consumer (함수형)
# - 로직이 단순함 -> 함수 사용
# - Fusion 결과를 받아서 블랙박스처럼 파일에 저장
# ==========================================

@app.consumer(source="SensorFusionNode", replicas=1)
def blackbox_logger(result):
    """
    퓨전 결과를 비동기로 파일에 기록합니다.
    (AI 추론 프로세스와 분리되어 있어서 메인 로직을 느리게 하지 않음)
    """
    ts = result["timestamp"]
    dist = result["distance"]
    obj = result["obstacle"]
    
    log_msg = f"[{ts:.3f}] Detect: {obj}, Dist: {dist}m"
    
    # 실제 파일 쓰기 or DB 적재
    # with open("driving_log.txt", "a") as f:
    #     f.write(log_msg + "\n")
        
    print(f"💾 [Log] {log_msg}") # 디버깅용 출력
    
    # 리턴값이 없으면 Gateway로 전송되지 않고 여기서 끝남 (Sink Node)
    return None


# ==========================================
# 4. Gateway (ROS2 연동)
# - 최종 판단 결과만 로봇 제어기로 전송
# ==========================================

@app.gateway(port=9999)
def ros_bridge(result):
    """
    TCP로 연결된 로봇(ROS2)에게 최종 명령 전송
    """
    # SensorFusionNode의 리턴값이 여기로 들어옴
    if result["distance"] < 1.0:
        cmd = {"cmd_vel": 0.0, "status": "EMERGENCY_STOP"}
    else:
        cmd = {"cmd_vel": 1.5, "status": "GO"}
        
    print(f"🚀 [Gateway] Sending to Robot: {cmd}")
    return cmd


# ==========================================
# 실행부
# ==========================================
if __name__ == "__main__":
    # 이 한 줄로:
    # 1. Redis Streams 생성 및 관리
    # 2. Time-Sync 알고리즘이 포함된 퓨전 프로세스 2개 구동
    # 3. 로깅 프로세스 1개 구동
    # 4. Gateway 서버 구동
    # 전부 자동으로 됨.
    app.run()