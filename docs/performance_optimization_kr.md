# 성능 최적화 가이드 (Performance Optimization)

EdgeFlow를 사용할 때 빌드 및 실행 속도를 최적화하는 방법을 안내합니다.

## 1. 빌드 속도 향상 (Build Speed)
기본적으로 EdgeFlow는 `linux/amd64` (PC용)와 `linux/arm64` (라즈베리파이용) 이미지를 동시에 빌드합니다.
하지만 PC(Windows/Mac x86)에서 라즈베리파이(ARM64) 이미지를 빌드할 때는 **QEMU 에뮬레이션**으로 인해 속도가 매우 느려질 수 있습니다 (특히 `torch` 설치 시).

### 해결책: 타겟 아키텍처 지정 (`--arch`)
배포하려는 기기에 맞는 아키텍처만 지정하여 빌드 시간을 단축할 수 있습니다.

```bash
# 라즈베리파이에만 배포할 경우 (추천)
edgeflow deploy main.py --arch linux/arm64

# PC(x86) 클러스터에만 배포할 경우
edgeflow deploy main.py --arch linux/amd64
```

이렇게 하면 불필요한 아키텍처 빌드를 건너뛰어 속도가 **2배 이상 향상**됩니다.

---

## 2. 도커 레이어 캐싱 (Docker Layer Caching)
`builder.py`는 `uv pip install --system`을 사용하여 패키지를 설치합니다. `node.toml`의 `dependencies`가 변경되지 않으면 도커 레이어 캐시를 재사용하므로 두 번째 빌드부터는 빠릅니다.

## 3. 베이스 이미지 최적화
가능하면 무거운 라이브러리(`torch`, `opencv`)가 미리 설치된 커스텀 베이스 이미지를 만들어서 `node.toml`의 `base` 이미지로 지정하는 것이 좋습니다.

```toml
# node.toml
base = "my-registry/edgeflow-base:latest" 
```
