# EdgeFlow 클러스터 배포 가이드 (Kubernetes)

이 문서는 Kubernetes 클러스터에 EdgeFlow 파이프라인을 배포하는 방법을 설명합니다.

> **로컬 실행부터 시작하려면**: [README](README_kr.md)를 먼저 참고하세요.

---

## 1. 사전 준비

### 1-1. Kubernetes 클러스터
- **Edge Device**: [K3s](https://k3s.io/) 권장 (가벼움)

```bash
# K3s 설치 (Linux)
curl -sfL https://get.k3s.io | sh -
```

### 1-2. Docker Hub 계정
EdgeFlow는 노드를 Docker 이미지로 빌드하여 Docker Hub에 푸시합니다.

```bash
# Docker Hub 로그인
docker login
```

---

## 2. EdgeFlow CLI 설치

```bash
# uv 설치
pip install uv

# EdgeFlow CLI 설치
uv tool install git+https://github.com/seolgugu/edgeflow.git

# 환경 점검
edgeflow doctor
```

---

## 3. 예제 프로젝트 준비

```bash
git clone https://github.com/seolgugu/edgeflow.git
cd edgeflow/examples/tutorial
```

프로젝트 구조:
```
examples/tutorial/
├── main.py          # 파이프라인 정의
└── nodes/           # 노드 소스 코드
    ├── camera/
    ├── yolo/
    └── gateway/
```

---

## 4. 노드 라벨링 (Node Labeling)

파드가 적절한 노드에 스케줄링되도록 라벨을 설정합니다.

```bash
# 노드 이름 확인
kubectl get nodes

# Gateway용 라벨 (필수)
kubectl label nodes <your-node-name> edgeflow.io/role=infra

# Camera 노드용
kubectl label nodes <your-node-name> edgeflow.io/device=camera

# GPU 노드용
kubectl label nodes <your-node-name> edgeflow.io/device=gpu
```

---

## 5. 배포

### 5-1. All-in-One 배포 (권장)

```bash
# x86_64 (일반 서버)
edgeflow up main.py --registry docker.io/yourusername

# ARM64 (라즈베리파이 등)
edgeflow up main.py --registry docker.io/yourusername --arch linux/arm64

# 특정 노드만 배포
edgeflow up main.py --registry docker.io/yourusername -t yolo
```

### 5-2. 단계별 배포

```bash
# 1. 빌드만
edgeflow build main.py --registry docker.io/yourusername

# 2. 푸시만
edgeflow push main.py --registry docker.io/yourusername

# 3. 배포만
edgeflow deploy main.py
```

---

## 6. 상태 확인

### 파드 상태
```bash
kubectl get pods -n edgeflow

# 예상 출력:
# NAME                       READY   STATUS    RESTARTS   AGE
# redis-0                    1/1     Running   0          2m
# camera-xxx                 1/1     Running   0          30s
# yolo-xxx                   1/1     Running   0          30s
# gateway-xxx                1/1     Running   0          30s
```

### 로그 확인
```bash
edgeflow logs yolo -n edgeflow
```

### 대시보드 접속
```bash
# 서비스 확인
kubectl get svc -n edgeflow

# 출력 예시:
# gateway   NodePort   10.43.x.x   <none>   8000:30080/TCP
```

**URL:** `http://<NODE-IP>:30080/dashboard`

---

## 7. 개발 워크플로우

### Hot Reload (sync)

코드 수정 후 리빌드 없이 즉시 반영:

```bash
# 모든 노드 싱크
edgeflow sync main.py

# 특정 노드만 싱크
edgeflow sync main.py -t yolo
```

> **Note:** `requirements.txt`나 시스템 의존성 변경 시에는 `edgeflow up`으로 재빌드 필요

---

## 8. 정리

```bash
# EdgeFlow 리소스 정리
edgeflow clean

# 네임스페이스 완전 삭제
kubectl delete namespace edgeflow
```

---

## 트러블슈팅

| 증상 | 해결 방법 |
|------|----------|
| 이미지 Pull 실패 | `docker login` 확인, 이미지 이름 확인 |
| 파드 Pending | 노드 라벨 확인 (`kubectl get nodes --show-labels`) |
| Gateway 접속 안됨 | 방화벽에서 NodePort (30080) 허용 |
| Redis 연결 실패 | `kubectl get pods -n edgeflow`로 Redis 상태 확인 |

```bash
# 환경 전체 점검
edgeflow doctor
```
