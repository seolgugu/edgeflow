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
        worker_id = self.name
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{worker_id}] [DEBUG] Entering setup, importing libraries...", flush=True)
        try:
            import torch
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{worker_id}] [DEBUG] torch imported.")
            from ultralytics import YOLO
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{worker_id}] [DEBUG] ultralytics imported.")
        except BaseException as e:
             print(f"❌ Import failed: {e}", flush=True)
             import traceback
             traceback.print_exc()
             raise e
        
        """Load YOLOv5 Model"""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{worker_id}] [INFO] Loading YOLOv5n model...")
        
        try:
            # Load local model (packaged with the node)
            model_path = os.path.join(os.path.dirname(__file__), "yolov5n.pt")
            if not os.path.exists(model_path):
                print(f"⚠️ Model file not found at {model_path}, attempting download/fallback...")
                model_path = "yolov5n.pt" # Let ultralytics handle it

            self.model = YOLO(model_path)
            # self.model.to('cpu') # Ultralytics handles device automatically, respects 'device' arg if needed
            
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
            # 1. Decode Image
            if isinstance(frame_data, bytes):
                 im_array = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
            else:
                 im_array = frame_data 

            if im_array is None:
                return None

            # 2. Inference
            # Ultralytics YOLO returns a list of result objects
            results = self.model(im_array, imgsz=320, verbose=False)

            # 3. Render
            # plot() returns a BGR numpy array of the annotated image
            processed_frame_bgr = results[0].plot()
            
            # [Log] AI Processing Time
            total_time = time.time() - start_process_time
            # print(f"[{timestamp_str}] [{worker_id}] [COMPLETED] Inference Time: {total_time:.4f}s")
            
            return processed_frame_bgr

        except Exception as e:
            print(f"[{timestamp_str}] [{worker_id}] [ERROR] AI processing failed: {e}")
            return None
