from edgeflow import EdgeApp
import time
import numpy as np
import cv2

app = EdgeApp("test-app")

@app.producer(fps=10)
def camera():
    # 320x240 랜덤 노이즈 이미지 생성
    frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
    return frame

@app.consumer(replicas=1)
def ai(frame):
    # 이미지에 "Processed" 글자 쓰기
    cv2.putText(frame, "Processed", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    _, buf = cv2.imencode('.jpg', frame)
    return buf.tobytes()

@app.gateway(port=8000)
def view(frame):
    return frame

if __name__ == "__main__":
    import sys
    role = sys.argv[1] if len(sys.argv) > 1 else "producer"
    app.run(role)