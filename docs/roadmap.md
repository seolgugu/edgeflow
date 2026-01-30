# EdgeFlow 향후 로드맵 (Future Roadmap)

이 문서는 EdgeFlow의 향후 계획된 기능과 아키텍처 개선 사항을 기술합니다.

## 1. 동적 재설정 (Dynamic Reconfiguration)
현재 EdgeFlow는 시작 시 환경변수(`NODE_CONFIG`)를 주입받는 **정적 설정(Static Configuration)** 모델을 사용합니다. 모델의 신뢰도 임계값(Confidence Threshold)이나 카메라 노출값 등을 실행 중에 변경하기 위해 **동적 설정** 메커니즘을 도입할 계획입니다.

### 제안 아키텍처: Redis 설정 채널 (Redis Config Channel)
ROS2의 무거운 파라미터 서버(RPC 기반) 대신, 기존 Redis 인프라를 활용한 경량화된 방식을 제안합니다.

*   **메커니즘**: Redis Pub/Sub
*   **토픽**: `config/update`
*   **메시지 포맷**:
    ```json
    {
      "target_node": "yolo-v5-1", 
      "parameters": {
        "confidence_threshold": 0.7,
        "iou_threshold": 0.45
      }
    }
    ```

### 구현 계획
1.  **BaseNode 업데이트**: `EdgeNode`에 `config/update` 토픽 리스너 구현.
2.  **설정 핸들러**: 사용자 노드에서 오버라이딩 가능한 `on_config_change(key, value)` 훅 추가.
3.  **Gateway API**: 웹 대시보드에서 설정을 변경할 수 있도록 REST API 엔드포인트(예: `POST /api/config`) 추가.

---

## 2. 엄격한 설정 검증 (Strict Configuration Validation)
안정성과 개발 편의성을 높이기 위해, "문자열 기반(Stringly Typed)"의 JSON 파싱 방식을 "강타입(Strongly Typed)" 검증 방식으로 전환합니다.

### 제안 아키텍처: Pydantic 통합
*   **라이브러리**: `pydantic`
*   **검증 시점**: 노드 시작 시 (`__init__`)

### 구현 계획
1.  `NodeConfig`, `SourceLink`, `TargetLink`에 대한 스키마 모델 정의.
2.  `EdgeNode` 내부의 단순 `json.loads`를 `NodeConfig.parse_raw()`로 대체.
3.  필수 필드 누락이나 잘못된 QoS 값 등이 있을 경우, 명확한 에러 메시지와 함께 즉시 실패(Fail Fast)하도록 개선.


---

## 3. 개발자 경험 및 디버깅 (Developer Experience)
복잡한 파이프라인을 개발할 때 생산성을 높이기 위한 기능들입니다.

### A. 로컬 디버그 모드 (Single-Process Debugging)
현재 `edgeflow local`은 멀티프로세스를 사용하므로 IDE(VSCode, PyCharm)의 중단점(Breakpoint) 디버깅이 어렵습니다.
*   **기능**: `system.run(debug=True)` 옵션 추가.
*   **동작**: 모든 노드를 단일 프로세스/단일 스레드 내에서 순차적으로 실행. Redis 없이 메모리 큐(Python Queue)를 사용하여 즉시 실행 및 디버깅 가능.

### B. 순환 감지 (Loop Detection)
잘못된 와이어링으로 인해 데이터가 무한 루프(A->B->A)를 도는 것을 방지합니다.
*   **구현**: `system.run()` 실행 시점에 그래프 위상 정렬(Topological Sort)을 수행하여 사이클(Cycle)이 존재하는지 사전에 검사.

### C. 분산 추적 (Distributed Tracing)
데이터가 어디서 병목이 걸리는지, 어디서 유실되는지 추적합니다.
*   **Latency Tracing**: 각 노드 진입/진출 시점에 타임스탬프를 기록하여 Gateway에서 전체 파이프라인의 지연 시간(End-to-End Latency)을 시각화.
*   **Packet Dump**: 특정 토픽의 데이터를 파일로 저장하거나 재생(Replay)하는 기능.

