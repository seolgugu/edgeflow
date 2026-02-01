# examples/yolo/nodes/camera/__init__.py
"""
Camera node - Pure Raspberry Pi Camera (Picamera2)
No simulation fallback. Will fail if picamera2 is missing.
"""
import time
import os
import cv2
import numpy as np
from edgeflow.nodes import ProducerNode

class Camera(ProducerNode):
    

    def setup(self):
        self.hostname = os.getenv("HOSTNAME", "localhost")
        print(f"📸 [Camera] Initialized on host: {self.hostname}")
        
        from picamera2 import Picamera2
        # Initialize Picamera2 Directly
        self.picam = Picamera2()
        config = self.picam.create_preview_configuration()
        config["main"]["size"] = (320, 240)
        config["main"]["format"] = "RGB888"
        self.picam.start()
        print(f"📸 [Camera] Real PiCamera started at 320x240")

        self.frame_counter = 0

    def loop(self):
        self.frame_counter = (self.frame_counter + 1) % 1000000
        
        # Capture directly
        im_array = self.picam.capture_array()
        
        # Encode to JPEG
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
        _, encoded = cv2.imencode('.jpg', im_array, encode_param)
        return encoded.tobytes()

    def teardown(self):
        if hasattr(self, 'picam') and self.picam:
            self.picam.stop()
            print("📸 [Camera] PiCamera stopped.")
