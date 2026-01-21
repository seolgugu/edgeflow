# EdgeFlow (KR)

**EdgeFlow**는 Redis Pub/Sub을 기반으로 분산 데이터 처리 파이프라인을 쉽게 구축할 수 있도록 돕는 Python 프레임워크입니다. 비디오 스트리밍, AI 추론, 센서 퓨전 애플리케이션 개발에 최적화되어 있습니다.

[![Version](https://img.shields.io/badge/version-0.1.0-orange.svg)](pyproject.toml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Kubernetes](https://img.shields.io/badge/kubernetes-ready-326ce5.svg)](https://kubernetes.io/)

[🇺🇸 English](README.md) | [🇰🇷 Korean](README_kr.md)

---

## 시작하기 (Quick Start)

### 설치 (Installation)

```bash
git clone https://github.com/witdory/edgeflow.git
cd edgeflow
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

### 로컬 실행 방법

`main.py` 파일 생성 (아래 [예제](#코드-예제-mainpy) 참고).

**옵션 1: 올인원 모드 (추천)**
스레드(Thread)를 사용하여 모든 노드를 하나의 터미널에서 실행합니다. 개발 테스트에 적합합니다.
```bash
python main.py
```

**옵션 2: 분산 모드**
노드별로 별도의 터미널(프로세스)에서 실행합니다. 실제 분산 환경과 유사하게 동작합니다.
```bash
# 터미널 1
python main.py --node camera

# 터미널 2
python main.py --node gateway
```

**대시보드 접속:** http://localhost:8000/dashboard

---

## 핵심 개념 (Core Concepts)

EdgeFlow는 복잡한 분산 시스템을 '노드 클래스'로 추상화했습니다. 사용자는 **데이터 처리 로직**만 구현하면 되며, 통신/직렬화/배포는 프레임워크가 담당합니다.

### 1. 앱과 데코레이터 (`EdgeApp`)
시스템의 진입점입니다. `@app.node` 데코레이터를 사용하여 파이프라인을 정의합니다.

```python
from edgeflow import EdgeApp, RedisBroker

app = EdgeApp("my-robot", broker=RedisBroker())

@app.node(name="camera", type="producer", fps=30)
class MyCamera(ProducerNode): ...
```
- **name**: 노드의 고유 ID입니다.
- **type**: 노드의 역할 (`producer`, `consumer`, `fusion`, `gateway`)을 지정합니다.
- **kwargs**: 노드 초기화 시 전달할 설정값 (예: `fps`, `replicas`, `device`)입니다.

### 2. 노드 타입별 구현 방법

#### ProducerNode
데이터를 생성하는 역할 (카메라, 센서 등)을 합니다.
*   **구현 필수:** `produce(self)` 메소드.
*   **반환값:** `numpy.ndarray`, `bytes`, 또는 `Frame` 객체.
*   **주요 속성:** `self.fps` (데코레이터에서 설정한 값).

#### ConsumerNode
입력 데이터를 받아 처리하는 역할 (필터링, AI 추론)을 합니다.
*   **구현 필수:** `process(self, data)` 메소드.
*   **입력:** 구독한 토픽에서 들어온 원본 데이터(payload).
*   **반환:** 처리된 데이터 (출력 토픽으로 자동 전송됨) 또는 `None` (전송 생략).
*   **설정:** `configure()`에서 `self.input_topics`와 `self.output_topic`을 지정해야 합니다.

#### FusionNode
여러 센서 데이터를 **타임스탬프 기준**으로 동기화합니다.
*   **구현 필수:** `process(self, frames)` 메소드.
*   **입력:** 시간순으로 정렬된 프레임 리스트 (입력 토픽 순서대로).
*   **설정:**
    *   `self.input_topics`: 동기화할 토픽 리스트.
    *   `self.slop`: 허용할 최대 시간 오차 (초 단위, 예: 0.1).

#### GatewayNode
처리된 데이터를 외부로 내보냅니다.
*   **설정:** `configure()`에서 `self.add_interface()`를 사용해 프로토콜을 장착합니다.
*   **내장 인터페이스:** `WebInterface` (MJPEG 스트리밍, 대시보드 포함).

### 3. 흐름 연결 (Flow Chaining)
노드 내부에서 Topic 이름을 하드코딩하는 대신, `main.py`에서 데이터의 흐름을 명시적으로 정의할 수 있습니다.

```python
# 명시적 노드 연결: Camera -> Filter -> Gateway
app.link("camera").to("filter").to("gateway")
```

*   **가독성:** 데이터가 어떻게 흐르는지 코드로 한눈에 파악할 수 있습니다.
*   **유연성:** 노드 내부 코드를 수정하지 않고도 연결 순서를 바꿀 수 있습니다.
*   **프로토콜 자동 감지:** 노드 타입에 따라 Redis(큐)로 보낼지, TCP(직접 연결)로 보낼지 자동으로 결정합니다.

---

## 코드 예제 (`main.py`)

GPU 처리 노드와 웹 게이트웨이를 체인(`link`)으로 연결하는 실제 예제 코드입니다.

```python
import time
import numpy as np
import cv2
import os

from edgeflow import EdgeApp
from edgeflow.nodes import ProducerNode, ConsumerNode, GatewayNode
from edgeflow.nodes.gateway.interfaces.web import WebInterface
from edgeflow.comms import RedisBroker
from edgeflow.config import settings

# 앱 초기화
app = EdgeApp("test-distributed-system", broker=RedisBroker())

# 1. Producer: 가짜 카메라 (애니메이션 생성)
@app.node(name="fake_camera", type="producer", device="camera", fps=30)
class FakeCamera(ProducerNode):
    def configure(self):
        self.hostname = os.getenv("HOSTNAME", "unknown-host")

    def produce(self):
        # 움직이는 공 애니메이션 생성
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (30, 30, 30)
        
        t = time.time()
        cx = int(320 + 200 * np.sin(t * 2))
        cy = int(240 + 100 * np.cos(t * 2))
        cv2.circle(img, (cx, cy), 30, (0, 255, 255), -1)
        
        cv2.putText(img, f"Src: {self.hostname}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        return img

# 2. Consumer: GPU 처리 시뮬레이션
@app.node(name="gpu_processor", type="consumer", device="gpu", replicas=2)
class GpuProcessor(ConsumerNode):
    def configure(self):
        self.hostname = os.getenv("HOSTNAME", "unknown-host")

    def process(self, frame):
        processed_img = frame.copy()
        # 객체 인식 시뮬레이션 (박스 그리기)
        cv2.rectangle(processed_img, (150, 100), (490, 380), (0, 0, 255), 3)
        cv2.putText(processed_img, "AI DETECTED", (150, 90), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        return processed_img

# 3. Gateway: 웹 시각화
@app.node(name="gateway", type="gateway", node_port=30080)
class VideoGateway(GatewayNode):
    def configure(self):
        web = WebInterface(port=settings.GATEWAY_HTTP_PORT)
        self.add_interface(web)

# 4. 연결 및 실행
if __name__ == "__main__":
    # 체인 연결: 카메라 -> GPU -> 게이트웨이
    app.link("fake_camera").to("gpu_processor")
    app.link("gpu_processor").to("gateway")
    
    # 직접 연결: 카메라 -> 게이트웨이 (원본 영상 확인용)
    app.link("fake_camera").to("gateway")
    
    app.run()
```

---

## 배포 (Deployment)

### 노드 스케줄링 및 라벨링 (Node Scheduling)
EdgeFlow는 Kubernetes 라벨을 사용하여 각 노드를 적절한 머신에 배치합니다.
*   **인프라 (Redis/Gateway):** `edgeflow.io/role=infra` 라벨이 있는 노드에 배치됩니다.
*   **애플리케이션 노드:** `@app.node(device=...)`에 설정한 값과 일치하는 라벨이 있는 노드에 배치됩니다.

```bash
# 1. 인프라 노드 라벨링 (Redis & Gateway 용)
# 보통 마스터 노드나 별도의 관리 노드에 지정합니다.
kubectl label nodes <node-name> edgeflow.io/role=infra

# 2. 작업 노드 라벨링 (App 노드 용)
# 예: @app.node(..., device="camera")인 경우
kubectl label nodes <node-name> edgeflow.io/device=camera

# 예: @app.node(..., device="gpu")인 경우
kubectl label nodes <node-name> edgeflow.io/device=gpu
```

### Kubernetes (K3s, EKS, GKE)

EdgeFlow CLI를 사용하면 Docker 이미지 빌드부터 쿠버네티스 배포까지 한 번에 처리할 수 있습니다.

```bash
# 1. 배포 (이미지 빌드 -> 푸시 -> 매니페스트 적용)
edgeflow deploy main.py \
  --registry docker.io/your-username \
  --namespace edgeflow

# 2. 상태 확인
kubectl get pods -n edgeflow

# 3. 대시보드 접속
# http://<node-ip>:30080/dashboard
```

### 환경 변수 (Environment Variables)
`deploy` 명령어는 다음 환경 변수들을 자동으로 파드에 주입하여 서비스 디스커버리를 처리합니다.
*   `REDIS_HOST`, `REDIS_PORT`: Redis 접속 정보.
*   `GATEWAY_HOST`, `GATEWAY_TCP_PORT`: 내부 노드 간 통신 경로.
*   `NODE_NAME`: 현재 실행 중인 파드의 식별자.

---

## 고급 기능: 듀얼 레디스 (Dual Redis)

대용량 비디오 데이터를 처리할 때 안정성을 높이기 위해 **제어 평면**과 **데이터 평면**을 분리할 수 있습니다.

```python
from edgeflow.comms.brokers import DualRedisBroker

# 브로커만 교체하면 인프라가 자동으로 변경됩니다.
app = EdgeApp("app", broker=DualRedisBroker())
```
*   **Control Plane:** 일반 메시지/큐 관리 (기본 Redis).
*   **Data Plane:** 영상 데이터 전용 (별도 Redis Instance).
*   **자동 배포:** `edgeflow deploy` 명령어가 `DualRedisBroker`를 감지하면 자동으로 두 번째 Redis 인프라(`redis-data`)를 생성합니다.

---

## 로드맵 (Roadmap)

- [ ] **SinkNode**: 데이터 영구 저장 (DB/File).
- [ ] **Latency Tracing**: 프레임이 생성되어 끝까지 도달하는 시간과 병목 구간 추적.
- [ ] **Cycle Detection**: 무한 루프 연결(A -> B -> A) 방지 및 경고.
- [ ] **ROS2 Interface**: ROS2 브릿지 네이티브 지원.
- [ ] Prometheus 메트릭 연동
- [ ] Edge TPU 가속 지원

---

## 기여하기 (Contributing)
PR과 이슈 등록은 언제나 환영합니다!

## 라이선스 (License)
Apache 2.0 License - 자세한 내용은 [LICENSE](LICENSE) 파일을 참고하세요.
