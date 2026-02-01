#edgeflow/nodes/producer.py
"""
ProducerNode - 데이터 생성 노드 (카메라, 센서 등)

Arduino Pattern:
- setup(): 초기화
- loop(): 데이터 생성 및 반환 (return으로 Frame 전송)
"""
import time
from .base import EdgeNode
from ..comms import Frame


class ProducerNode(EdgeNode):
    """데이터를 생성하여 다운스트림으로 전송하는 노드"""
    node_type = "producer"
    
    def __init__(self, broker=None, fps=30, topic="default", queue_size=1, **kwargs):
        super().__init__(broker, **kwargs)
        self.fps = fps
        self.queue_size = queue_size
        self._frame_id = 0

    def loop(self):
        """
        [User Hook] 데이터를 생성하여 반환
        - return: 이미지/데이터 (자동으로 Frame으로 포장되어 전송됨)
        - return None: 루프 종료
        """
        raise NotImplementedError("ProducerNode requires loop() implementation")

    def _generate_error_frame(self, error_msg):
        """Generate a visual error frame using OpenCV with a Test Dog Image"""
        try:
            import cv2
            import numpy as np
            import os
            
            # 1. 기본 검은 배경 생성 (320x240)
            height, width = 240, 320
            img = np.zeros((height, width, 3), dtype=np.uint8)
            
            # ---------------------------------------------------------
            # [Added] 강아지 테스트 이미지 합성 로직
            # ---------------------------------------------------------
            dog_path = "debug_dog.jpg"
            
            # 2-1. 이미지가 없으면 다운로드 (최초 1회만 실행됨)
            if not os.path.exists(dog_path):
                try:
                    import urllib.request
                    # YOLO의 상징과도 같은 그 강아지 사진 URL
                    url = "https://raw.githubusercontent.com/pjreddie/darknet/master/data/dog.jpg"
                    urllib.request.urlretrieve(url, dog_path)
                    print(f"🐶 [Producer] Downloaded debug_dog.jpg for testing")
                except Exception as e:
                    print(f"⚠️ [Producer] Failed to download dog image: {e}")

            # 2-2. 이미지 읽기 및 합성
            if os.path.exists(dog_path):
                dog_img = cv2.imread(dog_path)
                if dog_img is not None:
                    # 원본 비율 유지하면서 너비 120px로 리사이징 (320x240에 맞게 축소)
                    d_h, d_w = dog_img.shape[:2]
                    target_w = 120
                    scale = target_w / d_w
                    target_h = int(d_h * scale)
                    
                    dog_resized = cv2.resize(dog_img, (target_w, target_h))
                    
                    # 우측 상단에 배치 (여백 5px)
                    x_offset = width - target_w - 5
                    y_offset = 5
                    
                    # 배경 범위를 벗어나지 않도록 클리핑
                    if y_offset + target_h < height and x_offset + target_w < width:
                        img[y_offset:y_offset+target_h, x_offset:x_offset+target_w] = dog_resized
            # ---------------------------------------------------------
            
            # 3. 에러 메시지 텍스트
            # Red Text "RUNTIME ERROR" (320x240 포맷에 맞게 조정)
            cv2.putText(img, "RUNTIME ERROR", (40, 100), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            # Error Details
            cv2.putText(img, str(error_msg), (20, 140), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            # Timestamp
            cv2.putText(img, time.strftime("%H:%M:%S"), (200, 220), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            
            _, encoded = cv2.imencode('.jpg', img)
            return encoded.tobytes()
            
        except ImportError:
            print(f"⚠️ [Producer] Cannot generate error frame (cv2/numpy missing)")
            return None
        except Exception as ex:
            print(f"⚠️ [Producer] Error generation failed: {ex}")
            return None

    def _setup(self):
        """[Internal] Override to handle setup failures gracefully"""
        try:
            super()._setup()
        except Exception as e:
            print(f"⚠️ [Producer] Setup failed: {e}")
            print(f"⚠️ [Producer] Enabling FALLBACK MODE (Dynamic Swap)")
            self._setup_error = str(e)
            # Dynamic Method Swap: Replace 'loop' with fallback logic
            self.loop = self._fallback_loop

    def _fallback_loop(self):
        """Fallback loop used when setup fails"""
        error_msg = getattr(self, '_setup_error', "Setup Failed")
        return self._generate_error_frame(f"SETUP ERR: {error_msg}")

    def _run_loop(self):
        """[Internal] FPS에 맞춰 loop() 반복 호출"""
        print(f"🚀 Producer started (FPS: {self.fps})")
        
        while self.running:
            start = time.time()
            raw_data = None
            
            try:
                # 사용자 loop() (또는 교체된 _fallback_loop) 실행
                raw_data = self.loop()
                
                if raw_data is None:
                    # None 리턴은 '정상 종료' 의미로 해석 (혹은 에러로 처리할 수도 있음)
                    # 여기서는 그냥 break 처리하거나, 에러 프레임을 보낼 수도 있음.
                    # 일단 None은 종료 신호로 유지.
                    # 하지만 에러 상황에서 None을 리턴하는 경우도 있으므로...
                    # 사용자가 명시적으로 None을 리턴하면 종료.
                    pass
                    
            except Exception as e:
                print(f"❌ [Producer] Runtime Error: {e}")
                raw_data = self._generate_error_frame(f"{type(e).__name__}")
                time.sleep(1.0) # Error throttling

            if raw_data is None:
                # 데이터가 없으면 스킵 (혹은 종료)
                # user loop returning None -> Stop
                if not isinstance(raw_data, (bytes, bytearray)): 
                     # Check if it was really a stop signal or just no data
                     # For now, let's keep legacy behavior: None means stop if not exception
                     if self.running:
                         break
            
            # Frame 포장
            if isinstance(raw_data, Frame):
                frame = raw_data
                if frame.frame_id == 0:
                    frame.frame_id = self._frame_id
            else:
                frame = Frame(
                    frame_id=self._frame_id, 
                    timestamp=time.time(), 
                    data=raw_data
                )
            
            self.send_result(frame)
            self._frame_id += 1
            
            # FPS 제어
            elapsed = time.time() - start
            time.sleep(max(0, (1.0 / self.fps) - elapsed))

class FrameworkErrorNode(ProducerNode):
    """
    Fallback node used when the actual node class fails to load (e.g. ImportError).
    Continuously broadcasts the error message as an image.
    """
    def __init__(self, error_msg="Unknown Error", **kwargs):
        super().__init__(**kwargs)
        self.error_msg = error_msg
        
    def loop(self):
        return self._generate_error_frame(f"LOAD FAIL: {self.error_msg}")