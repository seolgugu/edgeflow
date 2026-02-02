# examples/yolo/nodes/yolov5/__init__.py
"""
YOLOv5 Inference Node (torch.hub approach - matching prototype)
"""
import time
import os
import cv2
import numpy as np
from edgeflow.nodes import ConsumerNode

class YoloV5(ConsumerNode):
    """
    Real YOLOv5n Consumer Node using torch.hub.load (like original prototype)
    """
    def setup(self):
        worker_id = self.name
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{worker_id}] [INFO] Loading YOLOv5n model via torch.hub...", flush=True)
        
        import torch
        
        # Load model exactly like the prototype
        self.model = torch.hub.load('ultralytics/yolov5', 'yolov5n', pretrained=True)
        self.model.to('cpu')
        
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{worker_id}] [INFO] YOLOv5n model loaded successfully.", flush=True)

    def loop(self, frame_data):
        """
        Process frame with YOLOv5 (matching prototype logic)
        """
        worker_id = self.name
        start_total = time.time()

        try:
            # 1. Decode Image
            t0 = time.time()
            if isinstance(frame_data, bytes):
                im_array = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
            else:
                im_array = frame_data
            decode_time = time.time() - t0

            if im_array is None:
                return None

            # 2. Inference (size=320 like prototype)
            t1 = time.time()
            results = self.model(im_array, size=320)
            inference_time = time.time() - t1

            # 3. Render (returns RGB)
            t2 = time.time()
            processed_frame_rgb = results.render()[0]
            render_time = time.time() - t2
            
            # 4. Convert RGB -> BGR for OpenCV encoding
            # t3 = time.time()
            # processed_frame_bgr = cv2.cvtColor(processed_frame_rgb, cv2.COLOR_RGB2BGR)

            # 5. Encode to JPEG (quality 80)
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            _, encoded_frame = cv2.imencode('.jpg', processed_frame_rgb, encode_param)
            encode_time = time.time() - t2
            
            total_time = time.time() - start_total
            print(f"[{worker_id}] decode:{decode_time*1000:.1f}ms infer:{inference_time*1000:.1f}ms render:{render_time*1000:.1f}ms encode:{encode_time*1000:.1f}ms TOTAL:{total_time*1000:.1f}ms", flush=True)
            
            return encoded_frame.tobytes()

        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{worker_id}] [ERROR] AI processing failed: {e}")
            return None

