# examples/my-robot/nodes/yolo/__init__.py
"""YOLO processor node - ConsumerNode example (Arduino Pattern)"""

import time
import os
import cv2

from edgeflow.nodes import ConsumerNode


class YoloProcessor(ConsumerNode):
    """Fake GPU processor that adds detection overlay"""
    
    def setup(self):
        """한 번만 실행: 모델 로딩 등 초기화"""
        self.hostname = os.getenv("HOSTNAME", "localhost")
        print(f"🧠 [GPU] Initialized on host: {self.hostname}")

    def loop(self, frame):
        """반복 실행: 프레임 처리 및 반환"""
        processed = frame.copy()
        
        # Add fake detection box
        cv2.rectangle(processed, (150, 100), (490, 380), (0, 0, 255), 3)
        cv2.putText(processed, "AI DETECTED", (150, 90), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.putText(processed, f"Processed by: {self.hostname}", (10, 450), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Simulate processing delay
        time.sleep(0.2)
        
        return processed
