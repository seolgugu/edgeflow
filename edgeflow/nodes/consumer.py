#edgeflow/nodes/consumer.py
"""
ConsumerNode - 데이터 처리 노드 (AI, GPU 등)

Arduino Pattern:
- setup(): 초기화 (모델 로딩 등)
- loop(data): 데이터 처리 및 반환
"""
import os
from .base import EdgeNode
from ..comms import Frame


class ConsumerNode(EdgeNode):
    """업스트림에서 데이터를 받아 처리하는 노드"""
    node_type = "consumer"
    
    def __init__(self, broker, replicas=1, **kwargs):
        super().__init__(broker=broker, **kwargs)
        self.replicas = replicas

    def loop(self, data):
        """
        [User Hook] 데이터를 처리하여 반환
        - data: 업스트림에서 받은 이미지/데이터
        - return: 처리된 결과 (자동으로 다운스트림 전송)
        - return None: 해당 프레임 스킵
        """
        raise NotImplementedError("ConsumerNode requires loop(data) implementation")

    def _run_loop(self):
        """[Internal] Redis에서 데이터를 받아 loop() 반복 호출"""
        target_topic = self.input_topics[0] if self.input_topics else "default"
        print(f"🧠 Consumer started (Replicas: {self.replicas}), Input Topic: {self.input_topics}")

        while self.running:
            # Redis에서 데이터 가져오기
            packet = self.broker.pop(target_topic, timeout=1)
            if not packet:
                continue

            # 역직렬화
            frame = Frame.from_bytes(packet)
            if not frame:
                continue

            try:
                # 사용자 loop() 실행
                result = self.loop(frame.data)
                if result is None:
                    continue

                # 결과 포장
                out_img, out_meta = result if isinstance(result, tuple) else (result, {})
                resp = Frame(frame.frame_id, frame.timestamp, out_meta, out_img)
                self.send_result(resp)

            except Exception as e:
                print(f"⚠️ Consumer Error: {e}")