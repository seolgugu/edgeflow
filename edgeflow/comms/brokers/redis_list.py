#edgeflow/comms/brokers/redis_list.py
"""
Redis List-based Broker for high-performance, low-latency messaging.
- Uses RPUSH/LPOP for simple queue semantics
- Supports QoS via list size trimming
- Auto-reconnect on connection loss
- Topic-based messaging
"""
import redis
import time
import os
from typing import Dict, Optional
from .base import BrokerInterface


class RedisListBroker(BrokerInterface):
    """Redis List-based message broker (faster than Streams)"""
    
    def __init__(self, host=None, port=None, maxlen=100):
        self.host = host or os.getenv('REDIS_HOST', 'localhost')
        self.port = port or int(os.getenv('REDIS_PORT', 6379))
        self.maxlen = maxlen  # Default max list length
        self._redis = None
        self._topic_limits = {}  # topic -> max size
        self._last_seen_id = {}  # topic -> last processed frame_id (for REALTIME dedup)

    def _ensure_connected(self):
        """Ensure Redis connection, auto-reconnect if needed"""
        if self._redis is None:
            self._redis = self._connect()
        else:
            try:
                self._redis.ping()
            except (redis.ConnectionError, redis.TimeoutError):
                print(f"⚠️ Redis connection lost. Reconnecting...")
                self._redis = self._connect()
    
    def _connect(self):
        """Connect to Redis with exponential backoff"""
        wait_time = 1
        while True:
            try:
                r = redis.Redis(
                    host=self.host, 
                    port=self.port, 
                    socket_timeout=5,
                    socket_connect_timeout=5
                )
                r.ping()
                print(f"✅ Redis Connected: {self.host}:{self.port}")
                return r
            except redis.ConnectionError:
                print(f"⚠️ Redis Connection Failed ({self.host}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                wait_time = min(wait_time * 2, 30)

    def push(self, topic: str, data: bytes):
        """Add message to list (RPUSH + LTRIM for size control)"""
        if not data:
            return
        self._ensure_connected()
        try:
            # Get limit from local cache, or fetch from Redis (for distributed env)
            if topic not in self._topic_limits:
                limit_bytes = self._redis.get(f"edgeflow:meta:limit:{topic}")
                if limit_bytes:
                    self._topic_limits[topic] = int(limit_bytes)
            
            limit = self._topic_limits.get(topic, self.maxlen)
            
            # Use pipeline for atomic rpush+ltrim (reduces round-trips)
            pipe = self._redis.pipeline()
            pipe.rpush(topic, data)
            pipe.ltrim(topic, -limit, -1)
            pipe.execute()
        except Exception as e:
            print(f"Redis Push Error: {e}")

    def pop(self, topic: str, timeout: int = 1, **kwargs) -> Optional[bytes]:
        """
        Read message from list (BLPOP - blocking left pop)
        Returns oldest message first (FIFO order for DURABLE QoS)
        """
        self._ensure_connected()
        try:
            # BLPOP returns tuple (key, value) or None
            result = self._redis.blpop([topic], timeout=timeout)
            if result:
                return result[1]  # Return only the value
            return None
        except (redis.ConnectionError, redis.TimeoutError) as e:
            print(f"⚠️ Redis connection lost in pop: {e}")
            self._redis = None  # Force reconnect on next call
            return None
        except Exception as e:
            print(f"Redis Pop Error: {e}")
            return None

    def pop_latest(self, topic: str, timeout: int = 1, **kwargs) -> Optional[bytes]:
        """
        [QoS: REALTIME] Get the latest message.
        - With list size=1 (set by REALTIME QoS), blpop effectively gets the latest
        - Uses true blocking (no polling overhead)
        """
        self._ensure_connected()
        
        try:
            # BLPOP: True blocking, no CPU waste
            # With REALTIME QoS, list size is 1, so this always gets the latest
            result = self._redis.blpop([topic], timeout=timeout)
            if result:
                return result[1]
            return None
        except (redis.ConnectionError, redis.TimeoutError) as e:
            print(f"⚠️ Redis connection lost in pop_latest: {e}")
            self._redis = None  # Force reconnect on next call
            return None
        except Exception as e:
            print(f"Redis PopLatest Error: {e}")
            return None

    def trim(self, topic: str, size: int = 1):
        """Set max size for a topic's list"""
        self._ensure_connected()
        self._topic_limits[topic] = size
        try:
            # Also store in Redis for persistence
            self._redis.set(f"edgeflow:meta:limit:{topic}", size)
            # Immediately trim if needed
            self._redis.ltrim(topic, -size, -1)
        except Exception:
            pass

    def queue_size(self, topic: str) -> int:
        """Return list length"""
        self._ensure_connected()
        try:
            return self._redis.llen(topic)
        except Exception:
            return 0

    def get_queue_stats(self) -> Dict[str, Dict[str, int]]:
        """Return stats for all tracked topics"""
        self._ensure_connected()
        stats = {}
        try:
            meta_keys = self._redis.keys("edgeflow:meta:limit:*")
            
            for key in meta_keys:
                key_str = key.decode('utf-8')
                topic = key_str.replace("edgeflow:meta:limit:", "")
                
                limit_bytes = self._redis.get(key)
                limit = int(limit_bytes) if limit_bytes else self.maxlen
                current = self._redis.llen(topic)
                
                stats[topic] = {"current": current, "max": limit}
        except Exception as e:
            print(f"Redis Stats Error: {e}")
        return stats

    def reset(self):
        """Clear all edgeflow-related keys"""
        self._ensure_connected()
        try:
            # Only clear edgeflow metadata, not the actual queues
            meta_keys = self._redis.keys("edgeflow:meta:*")
            if meta_keys:
                self._redis.delete(*meta_keys)
        except Exception:
            pass

    # ========== Serialization Protocol ==========
    
    def to_config(self) -> dict:
        return {
            "__class_path__": f"{self.__class__.__module__}.{self.__class__.__name__}",
            "host": self.host,
            "port": self.port,
            "maxlen": self.maxlen
        }
    
    @classmethod
    def from_config(cls, config: dict) -> 'RedisListBroker':
        return cls(
            host=config.get("host"),
            port=config.get("port"),
            maxlen=config.get("maxlen", 100)
        )
