from edgeflow import Node

class ExampleNode(Node):
    def setup(self):
        print(f"[{self.name}] Setup complete!")

    def loop(self, data):
        # Process data here
        print(f"[{self.name}] Received: {data}")
        return data
