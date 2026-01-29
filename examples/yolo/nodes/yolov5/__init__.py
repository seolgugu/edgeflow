# examples/yolo/nodes/yolov5/__init__.py
"""
YOLOv5 Inference Node (Real Implementation)
Adapts user-provided prototype into EdgeFlow ConsumerNode
"""
import time
import os
import cv2
import numpy as np
from edgeflow.nodes import ConsumerNode

class YoloV5(ConsumerNode):

    """
    Real YOLOv5n Consumer Node
    """
    def setup(self):
        import torch
        """Load YOLOv5 Model"""
        worker_id = self.name
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{worker_id}] [INFO] Loading YOLOv5n model...")
        
        try:
            # 'ultralytics/yolov5' 저장소에서 'yolov5n'(Nano) 모델을 로드
            self.model = torch.hub.load('ultralytics/yolov5', 'yolov5n', pretrained=True)
            self.model.to('cpu') # User prototype uses CPU
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{worker_id}] [INFO] YOLOv5n model loaded successfully.")
        except Exception as e:
            import traceback
            print(f"❌ Failed to load model: {e}")
            traceback.print_exc()
            self.running = False

    def loop(self, frame_data):
        """
        Process frame with YOLOv5
        """
        start_process_time = time.time()
        worker_id = self.name
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            # 1. Decode Image (EdgeFlow passes raw bytes or numpy depending on serialization)
            # EdgeFlow `ConsumerNode` receives `frame.data`. Since `Frame` wraps bytes/objects...
            # If the producer sends encoded JPEG bytes, we decode. If numpy, we use directly.
            # Assuming producer sends numpy or encoded bytes.
            # User prototype expects bytes decoding.
            
            if isinstance(frame_data, bytes):
                 im_array = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
            else:
                 im_array = frame_data # Assuming upstream sends numpy

            if im_array is None:
                return None

            # 2. Inference (Resize to 320 as per prototype)
            results = self.model(im_array, size=320)

            # 3. Render
            # processed_frame_rgb = results.render()[0]
            # processed_frame_bgr = cv2.cvtColor(processed_frame_rgb, cv2.COLOR_RGB2BGR)
            
            # [Log] AI Processing Time
            total_time = time.time() - start_process_time
            # print(f"[{timestamp_str}] [{worker_id}] [COMPLETED] Inference Time: {total_time:.4f}s")
            
            return results.render()[0]

        except Exception as e:
            print(f"[{timestamp_str}] [{worker_id}] [ERROR] AI processing failed: {e}")
            return None
