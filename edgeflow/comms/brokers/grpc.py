# edgeflow/comms/grpc.py
import queue
import threading
from .base import BrokerInterface

# 검증 필요
# 1. gRPC 서버가 실행할 실제 로직 (Servicer)
class InternalReceiver(edgeflow_pb2_grpc.WorkerServicer):
    def __init__(self, buffer):
        self.buffer = buffer # 데이터를 넘겨줄 큐
        
    def SendData(self, request, context):
        # 외부에서 gRPC로 데이터를 쏘면, 여기로 들어옴
        # 데이터를 받아서 내부 큐(Buffer)에 쏙 집어넣음
        self.buffer.put(request.data)
        return edgeflow_pb2.Response(status="OK")

# 2. 브로커 (위장막)
class GrpcBroker(Broker):
    def __init__(self, port=50051):
        self.internal_buffer = queue.Queue() # [중요] 임시 저장소
        
        # 백그라운드에서 gRPC 서버 시동
        self.server = grpc.server(...)
        edgeflow_pb2_grpc.add_WorkerServicer_to_server(
            InternalReceiver(self.internal_buffer), self.server
        )
        self.server.add_insecure_port(f'[::]:{port}')
        
        # 별도 스레드에서 서버 실행 (메인 스레드는 방해 안 받게)
        t = threading.Thread(target=self.server.start, daemon=True)
        t.start()

    def push(self, topic, data):
        # 1. [Channel] 누구한테 전화 걸지 주소 입력 (연결선 만들기)
        # (주의: 실제로는 topic에 매핑된 Consumer의 IP를 찾아야 함)
        target_address = "localhost:50051" 
        
        # with 구문을 쓰면 통신 끝나고 자동으로 연결을 끊어줌 (리소스 관리)
        with grpc.insecure_channel(target_address) as channel:
            
            # 2. [Stub] 그쪽 서버의 함수 목록을 아는 '대리인' 생성
            # "... " 부분이 바로 이 줄입니다!
            stub = edgeflow_pb2_grpc.WorkerStub(channel)
            
            # 3. [Call] 대리인을 시켜서 원격 함수 실행 (데이터 전송)
            # (데이터를 Protobuf 규격인 FrameData로 포장해서 보냄)
            request_packet = edgeflow_pb2.FrameData(
                topic=topic, 
                payload=data
            )
            
            # 실제 전송 발생!
            response = stub.SendData(request_packet)

    def pop(self, topic, timeout=0.1):
        # ConsumerNode가 이 함수를 호출함
        # 사실은 gRPC 서버가 받아둔 데이터를 큐에서 꺼내줌
        try:
            return self.internal_buffer.get(timeout=timeout)
        except queue.Empty:
            return None