# examples/my-robot/nodes/yolo/__init__.py
"""YOLO processor node - ConsumerNode example"""

import time
import os
import cv2

from edgeflow.nodes import ConsumerNode


class YoloProcessor(ConsumerNode):
    """Fake GPU processor that adds detection overlay"""
    
    def configure(self):
        self.hostname = os.getenv("HOSTNAME", "localhost")
        print(f"🧠 [GPU] Initialized on host: {self.hostname}")

    def process(self, frame):
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
