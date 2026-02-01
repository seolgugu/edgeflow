import asyncio
import time
import uvicorn
import traceback
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from .base import BaseInterface
from collections import defaultdict
from ....comms import Frame
from ....utils.buffer import TimeJitterBuffer

class WebInterface(BaseInterface):
    def __init__(self, port=8000, buffer_delay=0.0):
        self.port = port
        self.app = FastAPI(title="EdgeFlow Viewer")
        self.latest_frame = None
        self.latest_meta = {}
        self.lock = asyncio.Lock() # 동시성 제어
        self.broker = None #dashboard에서 큐 상태 모니터링할때 필요
        self._custom_routes = []
        
        # [Error Handling] Load Static 'No Signal' Asset
        self.placeholder_img = None 
        try:
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            asset_path = os.path.join(current_dir, "assets", "no_signal.jpg")
            if os.path.exists(asset_path):
                with open(asset_path, "rb") as f:
                    self.placeholder_img = f.read()
                print(f"✅ [WebInterface] Loaded static 'No Signal' image ({len(self.placeholder_img)} bytes)")
            else:
                print(f"⚠️ [WebInterface] Static asset not found: {asset_path}")
        except Exception as e:
            print(f"⚠️ [WebInterface] Failed to load static asset: {e}")

        self.buffer_delay = buffer_delay
        self.buffers = defaultdict(lambda: TimeJitterBuffer(buffer_delay=self.buffer_delay))

        # [신규] FPS 추적용 변수
        self.frame_counts = defaultdict(int)  # topic -> count
        self.worker_frame_counts = defaultdict(lambda: defaultdict(int))  # topic -> worker_id -> count
        self.fps_stats = {}  # topic -> {"total": fps, "workers": {}}
        self.last_fps_calc_time = time.time()
        
        # [신규] WebSocket 클라이언트 관리
        self._websockets = set()

    def setup(self):
        # 라우트 등록
        from fastapi import WebSocket
        
        @self.app.websocket("/ws/stats")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self._websockets.add(websocket)
            try:
                while True:
                    await websocket.receive_text() # 연결 유지용 (Client가 뭐 안보내도 됨)
            except Exception:
                self._websockets.discard(websocket)

        self.app.add_api_route("/health", self.health_check, methods=["GET"])
        self.app.add_api_route("/api/status", self.get_status, methods=["GET"])
        self.app.add_api_route("/api/fps", self.get_fps, methods=["GET"])
        self.app.add_api_route("/api/resources", self.get_resources, methods=["GET"])
        self.app.add_api_route("/dashboard", self.dashboard, methods=["GET"])
        
        # Video Routes
        self.app.add_api_route("/", self.root, methods=["GET"])
        self.app.add_api_route("/video", self.video_feed_default, methods=["GET"])
        self.app.add_api_route("/video/{topic_name}", self.video_feed_topic, methods=["GET"])

        for r in self._custom_routes:
            self.app.add_api_route(
                path=r["path"], 
                endpoint=r["endpoint"], 
                methods=r["methods"]
            )
            print(f"  + Custom Route Added: {r['path']}", flush=True)

        print(f"🌍 WebInterface prepared on port {self.port}", flush=True)
        print("📋 Active Routes:", flush=True)
        for route in self.app.routes:
            methods = getattr(route, 'methods', ['WS'])
            print(f"  - [{methods}] {route.path}", flush=True)

    def set_broker(self, broker):
        self.broker = broker

    async def get_resources(self):
        """시스템 리소스 상태 (Queue, Buffer) 반환"""
        async with self.lock:
            # 1. Buffer Size
            buffer_stats = {
                topic: {"current": len(buf.heap), "max": buf.max_size}
                for topic, buf in self.buffers.items()
            }
            
            # 2. Redis Queue Size
            queue_stats = {}
            if self.broker:
                for topic in self.buffers.keys():
                    queue_stats[topic] = self.broker.queue_size(topic)
            
            return JSONResponse(content={
                "buffers": buffer_stats,
                "queues": queue_stats
            })

    async def root(self):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/dashboard")

    async def video_feed_default(self):
        return StreamingResponse(
            self.stream_generator("default"), 
            media_type="multipart/x-mixed-replace; boundary=frameboundary"
        )

    async def video_feed_topic(self, topic_name: str):
        return StreamingResponse(
            self.stream_generator(topic_name),
            media_type="multipart/x-mixed-replace; boundary=frameboundary"
        )

    async def on_frame(self, frame):
        # Gateway가 이 함수를 호출해서 데이터를 넣어줌
        async with self.lock:
            topic = frame.meta.get("topic", "default")
            # print(f"DEBUG: Frame received on topic '{topic}'", flush=True) # Too noisy
            
            if topic not in self.buffers:
                 print(f"🌟 [WebInterface] New Topic Detected: {topic}", flush=True)

            self.buffers[topic].push(frame)
            self.frame_counts[topic] += 1  # [신규] FPS 카운트
            
            # [신규] Worker FPS 카운트 (topic 하위에 그룹화)
            worker_id = frame.meta.get('worker_id')
            if worker_id:
                self.worker_frame_counts[topic][worker_id] += 1

            if frame.meta:
                if topic not in self.latest_meta:
                    self.latest_meta[topic] = {}
                self.latest_meta[topic].update(frame.meta)

    def route(self, path, methods=["GET"]):
        def decorator(func):
            self._custom_routes.append({
                "path": path, 
                "endpoint": func, 
                "methods": methods
            })
            return func
        return decorator


    async def stream_generator(self, topic):
        print(f"🎬 [Stream] Started for topic: {topic}", flush=True)
        last_data_time = time.time()
        timeout_threshold = 2.0  # 2초간 데이터 없으면 No Signal
        
        try:
            while True:
                data = None
                async with self.lock:
                    if topic in self.buffers:
                        data = self.buffers[topic].pop()

                if data:
                    last_data_time = time.time()
                    yield (b'--frameboundary\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + data + b'\r\n')
                    wait_time = 0.001 if self.buffer_delay == 0.0 else 0.01
                    await asyncio.sleep(wait_time)
                else:
                    # Timeout Check
                    if time.time() - last_data_time > timeout_threshold:
                        if self.placeholder_img:
                            yield (b'--frameboundary\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + self.placeholder_img + b'\r\n')
                        
                        await asyncio.sleep(0.5) # Throttle refresh rate
                    else:
                        await asyncio.sleep(0.01)
        except Exception as e:
            print(f"❌ [Stream] Error: {e}", flush=True)
        finally:
            print(f"🛑 [Stream] Stopped for topic: {topic}", flush=True)

    async def get_status(self):
        async with self.lock:
            return JSONResponse(content=self.latest_meta)

    async def health_check(self):
        return JSONResponse(content={"status": "ok"})

    # [신규] FPS 계산 및 API
    async def get_fps(self):
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_fps_calc_time
            if elapsed > 0:
                result = {}
                
                # Topic FPS with nested workers
                for topic, count in self.frame_counts.items():
                    total_fps = round(count / elapsed, 2)
                    workers_fps = {}
                    
                    # Calculate worker FPS under this topic
                    if topic in self.worker_frame_counts:
                        for worker_id, worker_count in self.worker_frame_counts[topic].items():
                            workers_fps[worker_id] = round(worker_count / elapsed, 2)
                    
                    result[topic] = {
                        "total": total_fps,
                        "workers": workers_fps
                    }
                
                # Reset counters
                self.frame_counts = defaultdict(int)
                self.worker_frame_counts = defaultdict(lambda: defaultdict(int))
                self.last_fps_calc_time = now
                self.fps_stats = result
                
            return JSONResponse(content=self.fps_stats)

    # [신규] Dashboard HTML 페이지
    async def dashboard(self):
        try:
            # 템플릿 파일 로드
            import os
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'dashboard.html')
            if not os.path.exists(template_path):
                return HTMLResponse(content=f"<h1>Error: Template not found at {template_path}</h1>", status_code=500)
                
            with open(template_path, 'r', encoding='utf-8') as f:
                html = f.read()
            return HTMLResponse(content=html)
        except Exception as e:
            return HTMLResponse(content=f"<h1>Internal Error: {str(e)}</h1>", status_code=500)

    async def run_loop(self):
        # Start uvicorn
        print("🚀 [WebInterface] Starting Uvicorn Server...", flush=True)
        config = uvicorn.Config(self.app, host="0.0.0.0", port=self.port, log_level="info")
        server = uvicorn.Server(config)
        
        # [신규] WebSocket 브로드캐스팅 태스크 시작
        asyncio.create_task(self._broadcast_stats())
        
        await server.serve()

    async def _broadcast_stats(self):
        """WebSocket 클라이언트에게 주기적으로 상태 전송"""
        print("📢 [WebInterface] Broadcasting task started", flush=True)
        from fastapi import WebSocketDisconnect
        while True:
            if self._websockets:
                try:
                    # 1. 상태 수집
                    stats = await self.get_stats_json()
                    
                    # 2. 브로드캐스팅
                    disconnected = []
                    # Fix: RuntimeError "Set changed size during iteration" -> Use list copy
                    for ws in list(self._websockets):
                        try:
                            await ws.send_json(stats)
                        except Exception:
                            disconnected.append(ws)
                    
                    # 3. 끊긴 연결 정리
                    if disconnected:
                        print(f"🔌 [WebInterface] Removing {len(disconnected)} disconnected clients", flush=True)
                        for ws in disconnected:
                            self._websockets.remove(ws)
                except Exception as e:
                    print(f"❌ [WebInterface] Broadcast Error: {e}", flush=True)
                    traceback.print_exc()
            
            await asyncio.sleep(0.1) # 10 FPS 업데이트

    async def get_stats_json(self):
        """한 번에 모든 상태(FPS, Buffer, Queue) 반환"""
        try:
            fps_data = await self._calculate_fps()
            
            async with self.lock:
                # 1. Buffer Stats
                buffer_stats = {
                    topic: {"current": len(buf.heap), "max": buf.max_size}
                    for topic, buf in self.buffers.items()
                }
                
                # 2. Redis Queue Stats (Dynamic Discovery)
                queue_stats = {}
                if self.broker:
                    queue_stats = self.broker.get_queue_stats()  # [변경] 동적 조회 사용
                
                # 3. Status Info
                status_info = self.latest_meta
                
                return {
                    "fps": fps_data,
                    "buffers": buffer_stats,
                    "queues": queue_stats,
                    "status": status_info
                }
        except Exception as e:
            print(f"❌ [WebInterface] Stats Calc Error: {e}", flush=True)
            return {}

    async def _calculate_fps(self):
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_fps_calc_time
            
            # [Fix] FPS 계산 전이라도 토픽 목록 확보 (비디오 카드 생성을 위해)
            for topic in self.buffers.keys():
                if topic not in self.fps_stats:
                    self.fps_stats[topic] = {"total": 0.0, "workers": {}}

            if elapsed >= 1.0:
                result = {}
                
                # Topic FPS with nested workers
                for topic, count in self.frame_counts.items():
                    total_fps = round(count / elapsed, 2)
                    workers_fps = {}
                    
                    # Calculate worker FPS under this topic
                    if topic in self.worker_frame_counts:
                        for worker_id, worker_count in self.worker_frame_counts[topic].items():
                            workers_fps[worker_id] = round(worker_count / elapsed, 2)
                    
                    result[topic] = {
                        "total": total_fps,
                        "workers": workers_fps
                    }
                
                # Reset counters
                self.frame_counts = defaultdict(int)
                self.worker_frame_counts = defaultdict(lambda: defaultdict(int))
                self.last_fps_calc_time = now
                self.fps_stats = result
            
            return self.fps_stats