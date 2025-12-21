# edgeflow/gateway_engine.py
import asyncio
import struct
import json

class BaseGateway:
    """사용자가 상속받아 쓸 수 있는 기본 템플릿"""
    def setup(self):
        """초기화 작업이 필요하면 오버라이드 하세요"""
        pass

    def on_message(self, frame, meta):
        """반드시 구현해야 함"""
        raise NotImplementedError("on_message 메소드를 구현해야 합니다.")