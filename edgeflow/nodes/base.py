#edgeflow/nodes/base.py
"""
Arduino-style Node Base Class
- setup(): 한 번만 실행되는 초기화 로직
- loop(): 반복 실행되는 메인 로직
"""
from abc import ABC, abstractmethod
import os
from ..comms import RedisBroker


class EdgeNode(ABC):
    """
    Base class for all edge nodes.
    
    Arduino Pattern:
    - setup(): Called once at startup (user override)
    - loop(): Called repeatedly (user override)
    """
    node_type = "generic"
    
    def __init__(self, broker=None, **kwargs):
        self.running = True
        self.__dict__.update(kwargs)
        if not hasattr(self, 'name'):
            self.name = os.getenv("NODE_NAME", self.__class__.__name__)
        self.hostname = os.getenv("HOSTNAME", "localhost")
        host = os.getenv("REDIS_HOST", "localhost")
        self.broker = broker

        # I/O protocol and handlers
        self.input_protocol = "redis"
        self.input_topics = []
        self.output_handlers = []

        if not self.broker:
            self.broker = RedisBroker(host)
            
        if not self.broker:
            self.broker = RedisBroker(host)
            
        # K8s Config Injection (includes Wiring)
        node_config_json = os.getenv("NODE_CONFIG")
        if node_config_json:
            import json
            try:
                config_data = json.loads(node_config_json)
                self.__dict__.update(config_data)
                print(f"🔌 [Config] Injected from Environment")
            except Exception as e:
                print(f"⚠️ Failed to apply NODE_CONFIG: {e}")

        # Apply wiring (from kwargs or injected config)
        self._apply_wiring(self.__dict__)

    def send_result(self, frame):
        """연결된 모든 핸들러에게 데이터 전송"""
        if not frame:
            return
        for handler in self.output_handlers:
            handler.send(frame)

    def _apply_wiring(self, config):
        """Apply wiring from config (sources/targets)"""
        from ..handlers import RedisHandler, TcpHandler
        from ..qos import QoS
        from ..config import settings
        
        # Sources (Input)
        # config['sources'] = [{'name': 'camera', 'qos': ...}]
        for src in config.get('sources', []):
            topic = src['name']
            qos = src.get('qos', QoS.REALTIME)
            if isinstance(qos, int): qos = QoS(qos)
            
            self.input_topics.append({'topic': topic, 'qos': qos})
                
        # Targets (Output)
        # config['targets'] = [{'name': 'yolo', 'protocol': 'redis', ...}]
        redis_topics = set()
        for tgt in config.get('targets', []):
            protocol = tgt.get('protocol', 'redis')
            target_name = tgt['name']
            
            if protocol == 'tcp':
                source_id = tgt.get('channel') or self.name
                gw_host = settings.GATEWAY_HOST
                gw_port = settings.GATEWAY_TCP_PORT
                handler = TcpHandler(gw_host, gw_port, source_id)
                self.output_handlers.append(handler)
                print(f"🔗 [Direct] {self.name} ==(TCP)==> {target_name} (ID: {source_id})")
            else:
                topic = self.name # Pub/Sub uses my name as topic
                
                # QoS determines queue size: REALTIME=1 (latest only), DURABLE=100 (buffer)
                target_qos = tgt.get('qos', QoS.REALTIME)
                if isinstance(target_qos, int): target_qos = QoS(target_qos)
                
                if target_qos == QoS.REALTIME:
                    queue_size = 1   # Only keep latest frame
                else:
                    queue_size = tgt.get('queue_size', 100)  # Buffer for processing
                
                if topic not in redis_topics:
                    handler = RedisHandler(self.broker, topic, queue_size=queue_size)
                    self.output_handlers.append(handler)
                    redis_topics.add(topic)
                    print(f"🔗 [Redis] {self.name} ==(QoS:{target_qos.name}, size:{queue_size})==> {target_name}")

    def execute(self):
        """노드 실행 전체 흐름 제어 (Template Method)"""
        self._setup()
        try:
            self._run_loop()
        except KeyboardInterrupt:
            print(f"🛑 {self.__class__.__name__} Stopped.")
        finally:
            self.teardown()

    def _setup(self):
        """[Internal] 프레임워크 초기화 + 사용자 setup() 호출"""
        self.setup()

    def setup(self):
        """[User Hook] 한 번만 실행되는 초기화 로직 (Arduino setup)"""
        pass

    @abstractmethod
    def _run_loop(self):
        """[Internal] 서브클래스에서 loop() 호출 방식 정의"""
        pass

    def loop(self):
        """[User Hook] 반복 실행되는 메인 로직 (Arduino loop)"""
        raise NotImplementedError("Subclass must implement loop()")

    def teardown(self):
        """[User Hook] 종료 시 정리 로직"""
        pass