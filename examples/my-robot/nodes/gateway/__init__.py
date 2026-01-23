# examples/my-robot/nodes/gateway/__init__.py
"""Gateway node - GatewayNode example"""

from edgeflow.nodes import GatewayNode
from edgeflow.nodes.gateway.interfaces.web import WebInterface
from edgeflow.config import settings


class VideoGateway(GatewayNode):
    """Web streaming gateway"""
    
    def configure(self):
        web = WebInterface(port=settings.GATEWAY_HTTP_PORT, buffer_delay=0.0)
        self.add_interface(web)
