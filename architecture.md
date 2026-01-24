# Edgeflow v0.2.0 Architecture

GitHub 및 Mermaid를 지원하는 마크다운 뷰어에서 렌더링됩니다.

---

## 1. Class Hierarchy (Arduino Pattern)

Edgeflow v0.2.0 uses an inheritance-based structure.

```mermaid
classDiagram
    class EdgeNode {
        +setup()
        +loop()
        +teardown()
        +send_result(Frame)
        #_run_loop()
    }

    class ProducerNode {
        +int fps
        +loop() Frame
        #_run_loop()
    }
    
    class ConsumerNode {
        +int replicas
        +loop(data) Frame
        #_run_loop()
    }
    
    class GatewayNode {
        +int tcp_port
        +add_interface()
        +setup()
        #_run_async()
    }

    EdgeNode <|-- ProducerNode
    EdgeNode <|-- ConsumerNode
    EdgeNode <|-- GatewayNode
```

---

## 2. System Blueprint & Lazy Loading

The `System` class uses the Blueprint pattern to manage `NodeSpec`s.

```mermaid
classDiagram
    class System {
        +specs
        +node(path) NodeSpec
        +link(NodeSpec) Linker
        +run()
    }

    class NodeSpec {
        +String path
        +Dict config
        +String name
    }

    class Linker {
        +to(target)
    }

    System "1" *-- "many" NodeSpec : manages
    System ..> Linker : creates
```

---

## 3. Execution Flow (Local Simulation)

Sequence of loading and executing nodes locally.

```mermaid
sequenceDiagram
    participant User
    participant System
    participant Loader
    participant Node
    participant Broker as Redis

    User->>System: run()
    
    Note over System: 1. Instantiation Phase
    System->>Loader: _load_node_class(path)
    Loader-->>System: NodeClass
    System->>Node: __init__()

    Note over System: 2. Wiring Phase
    System->>Node: Configure handlers

    Note over System: 3. Execution Phase
    System->>Node: execute() (Thread)
    Node->>Node: setup()
    
    loop Every Frame
        Node->>Node: loop()
        Node->>Broker: Push Data
    end
```

---

## 4. Deployment Flow (CLI)

How `edgeflow deploy` works.

```mermaid
flowchart LR
    subgraph Host [Developer PC]
        Main[main.py] -->|Inspect| CLI[edgeflow deploy]
        CLI -->|Read| Spec[NodeSpec]
    end

    subgraph Build [Build Process]
        Spec -->|Generate| Builder[builder.py]
        Builder -->|UV Install| Docker[Docker Image]
    end

    subgraph Cluster [Kubernetes]
        Docker -->|Deploy| Pod1[Pod: Camera]
        Docker -->|Deploy| Pod2[Pod: YOLO]
    end
```
