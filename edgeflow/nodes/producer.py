#edgeflow/nodes/producer.py
import time
from .base import EdgeNode
from ..comms import Frame  # 기존 Frame 재사용

class ProducerNode(EdgeNode):
    node_type = "producer"
    def __init__(self, broker, fps=30, topic="default", queue_size=1, **kwargs):
        super().__init__(broker, **kwargs)
        self.fps = fps
        self.queue_size = queue_size

    def produce(self):
        """사용자가 구현해야 할 메소드"""
        raise NotImplementedError

    def run(self):
        print(f"🚀 Producer started (FPS: {self.fps})")
        frame_id = 0
        while self.running:
            start = time.time()
            
            # 사용자 로직 실행
            raw_data = self.produce()
            if raw_data is None: break

            # Frame 포장 (기존 로직)
            if isinstance(raw_data, Frame):
                frame = raw_data
                if frame.frame_id == 0:
                    frame.frame_id = frame_id
            else:
                frame = Frame(frame_id=frame_id, timestamp=time.time(), data=raw_data)
            
            self.send_result(frame)
            
            frame_id += 1
            
            # FPS 제어 (테스트용 fps 제한 기능)
            elapsed = time.time() - start
            time.sleep(max(0, (1.0/self.fps) - elapsed))