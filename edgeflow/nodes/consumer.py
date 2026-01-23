#edgeflow/nodes/consumer.py
import os
from .base import EdgeNode
from ..comms import Frame

class ConsumerNode(EdgeNode):
    node_type = "consumer"
    def __init__(self, broker, replicas=1, **kwargs):
        super().__init__(broker=broker, **kwargs)
        self.replicas = replicas
        

    def setup(self):
        pass

    def process(self, data):
        """사용자가 구현해야 할 메소드"""
        raise NotImplementedError

    def run(self):
        target_topic = self.input_topics[0] if self.input_topics else "default"
        print(f"🧠 Consumer started (Replicas: {self.replicas}), Input Topic: {self.input_topics}")

        while self.running:
            # Redis에서 가져오기 (Consumer의 Input은 무조건 Redis 고정)
            packet = self.broker.pop(target_topic, timeout=1)
            if not packet: continue

            # 역직렬화
            frame = Frame.from_bytes(packet)
            if not frame: continue

            try:
                # 사용자 로직 실행
                result = self.process(frame.data)
                if result is None: continue

                # 결과 처리 (Tuple or Data)
                out_img, out_meta = result if isinstance(result, tuple) else (result, {})
                


                # Gateway 전송 (TCP)
                resp = Frame(frame.frame_id, frame.timestamp, out_meta, out_img)
                self.send_result(resp)

            except Exception as e:
                print(f"⚠️ Consumer Error: {e}")