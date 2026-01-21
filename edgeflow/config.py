#edgeflow/config.py
import os
from dataclasses import dataclass

from edgeflow.constants import REDIS_PORT, DATA_REDIS_PORT, GATEWAY_TCP_PORT, GATEWAY_HTTP_PORT, DATA_REDIS_HOST

@dataclass
class Config:
    # Redis 설정 (Control Plane)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", REDIS_PORT))

    # Data Redis 설정 (Data Plane)
    DATA_REDIS_HOST: str = os.getenv("DATA_REDIS_HOST", "localhost")
    DATA_REDIS_PORT: int = int(os.getenv("DATA_REDIS_PORT", DATA_REDIS_PORT))

    # Gateway 설정
    GATEWAY_HOST: str = os.getenv("GATEWAY_HOST", "localhost")
    GATEWAY_TCP_PORT: int = int(os.getenv("GATEWAY_TCP_PORT", GATEWAY_TCP_PORT))
    GATEWAY_HTTP_PORT: int = int(os.getenv("GATEWAY_HTTP_PORT", GATEWAY_HTTP_PORT))

# 전역 설정 객체
settings = Config()