# ⚡ EdgeFlow 성능 최적화 가이드

Edge AI 개발 시 가장 큰 병목인 **"Docker ARM64 빌드 속도"**와 **"배포 사이클"**을 획기적으로 줄이는 방법을 안내합니다.

## 1. 🚀 개발 속도 혁신: Sync Mode (New)

코드 한 줄 고치고 이미지 빌드(10분) -> 푸시(1분) -> 배포(30초)를 기다리는 것은 낭비입니다.
`edgeflow sync` 명령어를 사용하여 **1초 만에** 변경 사항을 실행 중인 노드에 반영하세요.

### 사용법
```bash
# 전체 노드 동기화
edgeflow sync examples/yolo/main.py

# 특정 노드만 동기화 (예: yolov5)
edgeflow sync examples/yolo/main.py --target yolov5
```

### 작동 원리
1.  로컬의 소스 코드(`nodes/yolo/*.py`)를 감지.
2.  실행 중인 Kubernetes 파드(`pod/yolo-xxx`)를 자동으로 찾음.
3.  `kubectl cp`로 파일만 전송.
4.  파이썬 프로세스 리로드 (필요 시 `kubectl delete pod`로 빠른 재시작).

> **주의**: `requirements.txt`나 `node.toml`의 의존성이 바뀌면 반드시 **재빌드**해야 합니다. Sync는 로직 수정용입니다.

---

## 2. 🏗️ 빌드 속도 최적화 (Cross-Compilation)

Windows/Mac(x86)에서 라즈베리파이(ARM64)용 이미지를 빌드하면 **QEMU 에뮬레이터**가 돌아가 속도가 10~20배 느려집니다. 특히 `torch`, `numpy` 설치 시 수십 분이 걸립니다.

### ✅ 해결책 A: Remote Builder (강력 추천)
라즈베리파이 자체를 빌드 머신으로 사용합니다. PC에서 명령을 내리면 파이가 대신 빌드합니다.

```bash
# 1. 라즈베리파이를 원격 빌더로 등록 (SSH 필요)
docker buildx create --name rpi-builder --driver docker-container --platform linux/arm64 ssh://pi@192.168.x.x

# 2. 빌더 사용 설정
docker buildx use rpi-builder

# 3. 빌드 실행 (PC에서 하듯이 똑같이)
edgeflow build ...
```
-> **결과**: 30분 걸리던 빌드가 **2~3분**으로 단축됩니다.

### ✅ 해결책 B: Base Image 전략 (진행 중)
무거운 라이브러리(`torch`, `opencv`)가 미리 설치된 베이스 이미지를 사용하면 컴파일 과정을 건너뛸 수 있습니다.

*   `node.toml`에서 `base_image` 옵션을 활용하거나,
*   EdgeFlow가 제공하는 `edgeflow/base-ai:arm64` 이미지를 사용하도록 설정합니다. (로드맵 v0.3 예정)

---

## 3. 📦 배포 최적화 (Layer Caching)

EdgeFlow는 Docker의 **Layer Caching**을 적극 활용합니다.

1.  **Base Layer**: OS + 무거운 라이브러리 (변경 드묾, 2GB)
2.  **App Layer**: 사용자 소스 코드 (자주 변경, 50MB)

최초 1회 배포 이후에는 **App Layer만 전송**되므로, `edgeflow push`가 10초 이내로 끝납니다.
항상 `requirements.txt` 변경은 신중하게 하시고, 가능한 한 소스 코드 위주로 개발하세요.
