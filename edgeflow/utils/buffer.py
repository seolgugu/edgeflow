import time
import heapq

class TimeJitterBuffer:
    """
    [공용 유틸리티] 타임스탬프 기반 지터 버퍼
    - buffer_delay > 0: 설정된 시간만큼 지연 재생 (Jitter 방지)
    - buffer_delay == 0: 들어오는 즉시 재생 (Low Latency)
    - max_size: 최대 버퍼 크기 (초과 시 가장 오래된 프레임 삭제, 메모리 누수 방지)
    """
    def __init__(self, buffer_delay=0.0, max_size=60):
        self.buffer_delay = buffer_delay
        self.max_size = max_size  # 30fps 기준 약 2초 분량
        self.heap = [] # (timestamp, data_bytes)

    def push(self, frame):
        # 버퍼 크기 제한 - 초과 시 가장 오래된 프레임 삭제
        while len(self.heap) >= self.max_size:
            heapq.heappop(self.heap)
        
        ts = frame.timestamp
        data = frame.get_data_bytes()
        heapq.heappush(self.heap, (ts, data))

    def pop(self):
        if not self.heap:
            return None

        # 1. 즉시 전송 모드
        if self.buffer_delay == 0.0:
            return heapq.heappop(self.heap)[1]

        # 2. 버퍼링 모드
        now = time.time()
        play_deadline = now - self.buffer_delay
        
        # [GC] 너무 오래된 데이터 삭제 (0.5초 이상 지연된 건 가망 없음)
        while self.heap and self.heap[0][0] < (play_deadline - 0.5):
            heapq.heappop(self.heap)

        if not self.heap:
            return None

        # 재생 시간 체크
        oldest_ts, data = self.heap[0]
        if oldest_ts <= play_deadline:
            heapq.heappop(self.heap)
            return data
        
        return None
    
    def clear(self):
        self.heap = []