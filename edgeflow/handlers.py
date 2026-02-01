import socket
import struct
import asyncio
import threading
import queue
import time

class RedisHandler:
    def __init__(self, broker, topic, queue_size=1):
        self.broker = broker
        self.topic = topic
        self.queue_size = queue_size

    def send(self, frame):
        # Redis 브로커를 통해 전송 (기존 Broker.push 재사용)
        self.broker.push(self.topic, frame.to_bytes())

        if self.queue_size > 0:
            self.broker.trim(self.topic, self.queue_size)

class TcpHandler:
    def __init__(self, host, port, source_id):
        self.host = host
        self.port = port
        self.source_id = source_id
        self.sock = None
        self.queue = queue.Queue(maxsize=10) # Prevent memory explosion
        self.worker_thread = None
        self.running = True
        
        # Start Worker Thread
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(1.0) 
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"✅ [TcpHandler] Connected to Gateway at {self.host}:{self.port}")
        except Exception:
            if self.sock:
                self.sock.close()
            self.sock = None

    def _worker(self):
        """Background thread for sending data"""
        while self.running:
            try:
                frame = self.queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if self.sock is None:
                self.connect()
            
            if self.sock:
                try:
                    # [Identity] Gateway 라우팅을 위해 소스 ID 주입
                    frame.meta["topic"] = self.source_id
                    packet_body = frame.to_bytes()
                    length_header = struct.pack('>I', len(packet_body))
                    
                    self.sock.sendall(length_header + packet_body)
                except Exception:
                    # Connection lost
                    self.sock.close()
                    self.sock = None
            
            self.queue.task_done()

    def send(self, frame):
        """Non-blocking put into queue"""
        try:
            # If queue is full, drop oldest to maintain real-time
            if self.queue.full():
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    pass
            self.queue.put_nowait(frame)
        except Exception:
            pass

    def close(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
        if self.sock:
            self.sock.close()