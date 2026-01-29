# examples/yolo/nodes/gateway/__init__.py
from edgeflow.nodes import GatewayNode
from edgeflow.nodes.gateway.interfaces.web import WebInterface
from edgeflow.config import settings

class VideoGateway(GatewayNode):
    """Web streaming gateway"""
    def setup(self):
        # Use default port from settings (8000)
        web = WebInterface(port=settings.GATEWAY_HTTP_PORT, buffer_delay=0.0)
        self.add_interface(web)
