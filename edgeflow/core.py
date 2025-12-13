import time
import os
import asyncio
import logging
from .comms import RedisBroker, GatewaySender
import struct

# 로거 설정
logging.basicConfig(level=logging.INFO, format='[%(name)s] %(message)s')
logger = logging.getLogger("EdgeFlow")

class EdgeApp:
    def __init__(self, name):
        self.name = name
        self.producer_func = None
        self.consumer_func = None
        self.gateway_func = None
        self.mode = "stream"
        self.fps = 30
        self.replicas = 1

    # --- Decorators ---
    def producer(self, mode="stream", fps=30):
        def decorator(func):
            self.producer_func = func
            self.mode = mode
            self.fps = fps
            return func
        return decorator

    def consumer(self, replicas=1):
        def decorator(func):
            self.consumer_func = func
            self.replicas = replicas
            return func
        return decorator

    def gateway(self, port=8000):
        def decorator(func):
            self.gateway_func = func
            self.gateway_port = port
            return func
        return decorator

    # --- Runtime Entrypoint ---
    def run(self, role):
        redis_host = os.getenv("REDIS_HOST", "localhost")
        
        if role == "producer":
            self._run_producer(redis_host)
        elif role == "consumer":
            self._run_consumer(redis_host)
        elif role == "gateway":
            self._run_gateway()
        else:
            logger.error(f"Unknown role: {role}")

    # --- Internal Loops ---
    def _run_producer(self, host):
        broker = RedisBroker(host)
        logger.info(f"🚀 Producer 시작 (Mode: {self.mode}, FPS: {self.fps})")
        frame_id = 0
        while True:
            start = time.time()
            try:
                frame_data = self.producer_func() # 사용자 함수 실행

                # 데이터 소진 처리
                if frame_data is None:
                    if self.mode == "batch":
                        logger.info("✅ Batch 완료. 종료 신호(EOF) 전송.")
                        for _ in range(self.replicas): 
                            broker.push(b"EOF")
                        break
                    else:
                        logger.warning("⚠️ 스트림 끊김. 재시도...")
                        time.sleep(1); 
                        continue


                timestamp = time.time()
                header = struct.pack('!Id', frame_id, timestamp)
                packet = header + frame_data

                frame_id += 1
                elapsed = time.time() - start

                if self.mode == "realtime":
                    broker.push(packet)
                    broker.trim(1) # 최신 상태 유지
                    time.sleep(max(0, (1.0/self.fps) - elapsed))
                elif self.mode == "ordered":
                    time.sleep(max(0, (1.0/self.fps) - elapsed))
                elif self.mode == "batch"  :
                    pass

            except Exception as e:
                logger.error(f"Producer User Function Error: {e}")
                time.sleep(1)
                continue
                

    def _run_consumer(self, host):
        broker = RedisBroker(host)
        gw_host = os.getenv("GATEWAY_HOST", "localhost")
        sender = GatewaySender(gw_host)
        logger.info(f"🧠 Consumer 시작 (Replicas: {self.replicas})")

        while True:
            packet = broker.pop()

            if not packet:
                continue
            if packet == b"EOF":
                logger.info("🛑 종료 신호(EOF) 수신. 종료합니다.")
                break
            if len(packet) < 12: 
                continue

            # frame_id, timestamp = struct.unpack('!Id', packet[:12])
            frame_data = packet[12:]
            header = packet[:12]

            if frame_data:
                try:
                    result_img = self.consumer_func(frame_data) # 사용자 정의 AI 함수

                    if result_img: 
                        sender.send(header + result_img)

                except Exception as e:
                    logger.error(f"Consumer User Function Error: {e}")


            
            
            

    def _run_gateway(self):
        import uvicorn
        from fastapi import FastAPI
        from fastapi.responses import StreamingResponse
        
        app = FastAPI()
        q = asyncio.Queue(maxsize=1)

        async def tcp_server(reader, writer):
            while True:
                try:
                    len_bytes = await reader.readexactly(4)
                    length = int.from_bytes(len_bytes, 'big')
                    data = await reader.readexactly(length)
                    
                    final = self.gateway_func(data) if self.gateway_func else data
                    if final:
                        if q.full(): q.get_nowait()
                        await q.put(final)
                except asyncio.IncompleteReadError: break
                except Exception as e: logger.error(f"Gateway TCP Error: {e}")

        async def mjpeg_gen():
            while True:
                packet = await q.get()
                frame_data = packet[12:]
                yield (b'--frameboundary\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')

        @app.get("/video_stream")
        def stream():
            return StreamingResponse(mjpeg_gen(), media_type="multipart/x-mixed-replace; boundary=frameboundary")

        @app.on_event("startup")
        async def startup():
            asyncio.create_task(asyncio.start_server(tcp_server, '0.0.0.0', 8080))

        logger.info(f"📺 Gateway 시작 (HTTP: {self.gateway_port})")
        uvicorn.run(app, host="0.0.0.0", port=self.gateway_port)