# edgeflow/constants.py

# K8s 내부에서 사용할 고정된 서비스 도메인 이름
REDIS_HOST = "edgeflow-redis-service"
REDIS_PORT = 6379
DATA_REDIS_HOST = "edgeflow-redis-data-service" # [신규] 고정 호스트명
DATA_REDIS_PORT = 6380

GATEWAY_TCP_PORT = 8080
GATEWAY_HTTP_PORT = 8000