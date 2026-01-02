#edgeflow/comms/brokers/hybrid.py
import zmq
import threading
import pickle
import time
from collections import deque
from .base import BrokerInterface
from .redis_broker import RedisBroker # 기존 브로커 상속 혹은 포함

class HybridBroker(BrokerInterface):
    def __init__(self, redis_host='localhost', redis_port=6379, zmq_port=5555):
        # 1. Redis 연결 (신호용)
        self.redis = RedisBroker(host=redis_host, port=redis_port)
        
        # 2. ZMQ 설정 (데이터용)
        self.context = zmq.Context()
        
        # [송신용] PUB 소켓 (데이터 뿌리기)
        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.bind(f"tcp://*:{zmq_port}")
        
        # [수신용] SUB 소켓 (데이터 받기)
        self.sub_socket = self.context.socket(zmq.SUB)
        # 실제 분산 환경에선 프로듀서 IP를 적어야 함 (여기선 로컬 가정)
        self.sub_socket.connect(f"tcp://localhost:{zmq_port}") 
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "") # 모든 토픽 수신
        
        # 3. 데이터 버퍼 (ID: Data 매핑용)
        self.local_buffer = {} 
        self.buffer_lock = threading.Lock()
        
        # 4. 백그라운드 수신 스레드 시작
        self.running = True
        self.listener = threading.Thread(target=self._zmq_listener, daemon=True)
        self.listener.start()

    def _zmq_listener(self):
        """백그라운드에서 ZMQ 데이터를 계속 받아서 버퍼에 저장"""
        while self.running:
            try:
                # ZMQ 패킷 구조: [Topic, Frame_ID, Data]
                # 여기선 간단히 pickle로 통째로 받았다고 가정
                raw_msg = self.sub_socket.recv(flags=zmq.NOBLOCK)
                payload = pickle.loads(raw_msg)
                
                frame_id = payload['frame_id']
                topic = payload['topic']
                
                with self.buffer_lock:
                    # 버퍼에 저장 (키: "topic:frame_id")
                    key = f"{topic}:{frame_id}"
                    self.local_buffer[key] = payload['data']
                    
                    # (옵션) 버퍼 관리: 너무 오래된 데이터 삭제 로직 필요
                    
            except zmq.Again:
                time.sleep(0.001) # 데이터 없으면 잠깐 쉼
            except Exception as e:
                print(f"ZMQ Error: {e}")

    def push(self, topic, frame_bytes):
        """
        데이터는 ZMQ로, 신호는 Redis로!
        """
        # 1. 프레임 바이트에서 ID 추출 (구조체 파싱 필요하지만 여기선 가정)
        # 실제론 Frame 객체를 받거나, bytes 앞부분 헤더를 읽어야 함
        # 편의상 frame_bytes가 딕셔너리라고 가정하고 설명합니다.
        # 실제 구현시엔 Frame.from_bytes()를 잠깐 해서 ID만 따야 함.
        
        # 예시 데이터 구조: {'frame_id': 100, 'topic': 'cam', 'data': ...}
        import pickle
        frame_obj = pickle.loads(frame_bytes) # (비효율적이지만 예시를 위해)
        frame_id = frame_obj.frame_id
        
        # 2. Heavy Data -> ZMQ Broadcast
        payload = {
            'topic': topic,
            'frame_id': frame_id,
            'data': frame_bytes # 통째로 전송
        }
        self.pub_socket.send(pickle.dumps(payload))
        
        # 3. Light Signal -> Redis Queue
        # Redis에는 "ID"만 보냄 (아주 가벼움!)
        signal = f"{frame_id}".encode('utf-8')
        self.redis.push(topic, signal)

    def pop(self, topic, timeout=0.1):
        """
        Redis에서 신호(ID)를 받고, 로컬 버퍼에서 데이터를 찾음
        """
        # 1. Redis에서 티켓(ID) 꺼내기
        signal = self.redis.pop(topic, timeout=timeout)
        if not signal:
            return None
            
        target_id = int(signal.decode('utf-8'))
        target_key = f"{topic}:{target_id}"
        
        # 2. ZMQ 버퍼에 데이터가 도착했는지 확인 (Spin-lock or Wait)
        start_wait = time.time()
        while time.time() - start_wait < 0.2: # 최대 0.2초 대기
            with self.buffer_lock:
                if target_key in self.local_buffer:
                    # 데이터 찾음! 꺼내고 삭제
                    data = self.local_buffer.pop(target_key)
                    return data
            time.sleep(0.001) # ZMQ 스레드가 채워줄 때까지 대기
            
        print(f"⚠️ Data missing for Ticket {target_id} (ZMQ Lag?)")
        return None
        
    def trim(self, topic, size):
        self.redis.trim(topic, size)