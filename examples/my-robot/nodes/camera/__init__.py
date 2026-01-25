# examples/my-robot/nodes/camera/__init__.py
"""Camera node - ProducerNode example (Arduino Pattern)"""

import time
import os
import numpy as np
import cv2

from edgeflow.nodes import ProducerNode


class Camera(ProducerNode):
    """Fake camera that produces animated ball frames"""
    
    def setup(self):
        """한 번만 실행: 초기화"""
        self.hostname = os.getenv("HOSTNAME", "localhost")
        print(f"📸 [Camera] Initialized on host: {self.hostname}")

    def loop(self):
        """반복 실행: 프레임 생성 및 반환"""
        # Create dark background
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (30, 30, 30)
        
        # Animated ball
        t = time.time()
        cx = int(320 + 200 * np.sin(t * 2))
        cy = int(240 + 100 * np.cos(t * 2))
        cv2.circle(img, (cx, cy), 30, (0, 255, 255), -1)  # Yellow ball
        
        # Overlay info
        cv2.putText(img, f"Src: {self.hostname}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(img, f"Time: {t:.2f}", (10, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return img
