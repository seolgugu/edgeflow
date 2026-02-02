# edgeflow/comms/brokers/dual_redis_list.py
"""
Dual Redis List-based Broker
- Control Redis: List for message ordering (lightweight frame_id references)
- Data Redis: Blob storage for large payloads
- Uses RPUSH/LPOP for high-performance, low-latency messaging
"""
import redis
import redis.exceptions
import struct
import time
import os
from typing import Dict, Optional
from .base import BrokerInterface
from ...config import settings


class DualRedisListBroker(BrokerInterface):
    """
    Dual Redis List Broker:
    - ctrl_redis: Lightweight list (frame_id references)
    - data_redis: Heavy data storage (actual frames)
    """
    
    def __init__(self, ctrl_host=None, ctrl_port=None, 
                       data_host=None, data_port=None, maxlen=100):
        
        self.ctrl_host = ctrl_host or settings.REDIS_HOST
        self.ctrl_port = ctrl_port or settings.REDIS_PORT
        self.data_host = data_host or settings.DATA_REDIS_HOST
        self.data_port = data_port or settings.DATA_REDIS_PORT
        self.maxlen = maxlen
        
        self.ctrl_redis = None
        self.data_redis = None
        self._topic_limits = {}  # topic -> max size
        self._last_seen_id = {}  # topic -> last processed frame_id (for REALTIME dedup)

    def _ensure_connected(self):
        """Ensure both Redis connections, auto-reconnect if needed"""
        if self.ctrl_redis is None:
            self.ctrl_redis = self._connect(self.ctrl_host, self.ctrl_port, "Control")
        else:
            try:
                self.ctrl_redis.ping()
            except (redis.ConnectionError, redis.TimeoutError):
                print(f"⚠️ Control Redis connection lost. Reconnecting...")
                self.ctrl_redis = self._connect(self.ctrl_host, self.ctrl_port, "Control")
        
        if self.data_redis is None:
            self.data_redis = self._connect_data_redis()
        else:
            try:
                self.data_redis.ping()
            except (redis.ConnectionError, redis.TimeoutError):
                print(f"⚠️ Data Redis connection lost. Reconnecting...")
                self.data_redis = self._connect_data_redis()

    def _connect(self, host, port, name="Redis"):
        """Connect to Redis with exponential backoff"""
        wait_time = 1
        while True:
            try:
                r = redis.Redis(
                    host=host, 
                    port=port, 
                    socket_timeout=5,
                    socket_connect_timeout=5
                )
                r.ping()
                print(f"✅ {name} Redis Connected: {host}:{port}")
                return r
            except redis.ConnectionError:
                print(f"⚠️ {name} Redis Connection Failed ({host}:{port}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                wait_time = min(wait_time * 2, 30)

    def _connect_data_redis(self):
        """Connect to Data Redis with fallback to Control Redis"""
        r = redis.Redis(
            host=self.data_host, 
            port=self.data_port, 
            socket_connect_timeout=0.5
        )
        
        # For non-localhost, always use configured host
        if self.data_host not in ("localhost", "127.0.0.1"):
            try:
                r.ping()
                print(f"✅ Data Redis Connected: {self.data_host}:{self.data_port}")
                return r
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
                return self._connect(self.data_host, self.data_port, "Data")
        
        # For localhost, try Data Redis first, fallback to Control Redis
        try:
            r.ping()
            print(f"✅ Data Redis Connected: {self.data_host}:{self.data_port}")
            return r
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
            print(f"⚠️ [DualRedis] Failed to connect to Data Redis at {self.data_host}:{self.data_port}.")
            print(f"🔄 [DualRedis] Falling back to Control Redis port ({self.ctrl_port}) for local testing.")
            return self.ctrl_redis  # Use same connection as Control

    def reset(self):
        """Reset Broker State (FLUSHALL)"""
        self._ensure_connected()
        try:
            self.ctrl_redis.flushall()
            if self.ctrl_redis != self.data_redis:
                self.data_redis.flushall()
            print("🧹 [DualRedisListBroker] System Reset: FLUSHALL executed")
        except Exception as e:
            print(f"⚠️ [DualRedisListBroker] Failed to reset: {e}")

    def push(self, topic: str, frame_bytes: bytes):
        """
        Store data in Data Redis, push frame_id reference to Control Redis List
        """
        if not frame_bytes or len(frame_bytes) < 4:
            return
        
        self._ensure_connected()
        
        # Get limit from local cache, or fetch from Redis (for distributed env)
        if topic not in self._topic_limits:
            limit_bytes = self.ctrl_redis.get(f"edgeflow:meta:limit:{topic}")
            if limit_bytes:
                self._topic_limits[topic] = int(limit_bytes)
        
        limit = self._topic_limits.get(topic, self.maxlen)
        
        # Extract frame_id from header
        frame_id = struct.unpack('!I', frame_bytes[:4])[0]
        data_key = f"{topic}:data:{frame_id}"
        
        try:
            # Optimization: If Ctrl and Data are same instance, use single pipeline
            if self.ctrl_redis == self.data_redis:
                pipe = self.ctrl_redis.pipeline()
                pipe.set(data_key, frame_bytes, ex=60)  # 60s TTL
                pipe.rpush(topic, str(frame_id))
                pipe.ltrim(topic, -limit, -1)
                pipe.execute()
            else:
                # Separate instances
                self.data_redis.set(data_key, frame_bytes, ex=60)
                self.ctrl_redis.rpush(topic, str(frame_id))
                self.ctrl_redis.ltrim(topic, -limit, -1)
        except (redis.ConnectionError, redis.TimeoutError) as e:
            print(f"⚠️ Redis connection lost in push: {e}")
            self.ctrl_redis = None
            self.data_redis = None
        except Exception as e:
            print(f"DualRedisListBroker Push Error: {e}")

    def pop(self, topic: str, timeout: int = 1, **kwargs) -> Optional[bytes]:
        """
        Read frame_id from list (BLPOP), fetch data from Data Redis
        For DURABLE QoS - processes all messages in order
        """
        self._ensure_connected()
        
        try:
            # BLPOP returns (key, value) or None
            result = self.ctrl_redis.blpop([topic], timeout=timeout)
            if not result:
                return None
            
            frame_id = result[1].decode('utf-8')
            
            # Fetch actual data from Data Redis
            data_key = f"{topic}:data:{frame_id}"
            raw_data = self.data_redis.get(data_key)
            
            return raw_data if raw_data else None
        except (redis.ConnectionError, redis.TimeoutError) as e:
            print(f"⚠️ Redis connection lost in pop: {e}")
            self.ctrl_redis = None
            self.data_redis = None
            return None
        except Exception as e:
            print(f"DualRedisListBroker Pop Error: {e}")
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
            result = self.ctrl_redis.blpop([topic], timeout=timeout)
            if not result:
                return None
            
            # Decode frame_id
            frame_id = result[1].decode('utf-8') if isinstance(result[1], bytes) else result[1]
            
            # Fetch actual data from Data Redis
            data_key = f"{topic}:data:{frame_id}"
            raw_data = self.data_redis.get(data_key)
            
            return raw_data if raw_data else None
        except (redis.ConnectionError, redis.TimeoutError) as e:
            print(f"⚠️ Redis connection lost in pop_latest: {e}")
            self.ctrl_redis = None
            self.data_redis = None
            return None
        except Exception as e:
            print(f"DualRedisListBroker PopLatest Error: {e}")
            return None

    def trim(self, topic: str, size: int = 1):
        """Set max size for a topic's list"""
        self._ensure_connected()
        self._topic_limits[topic] = size
        try:
            self.ctrl_redis.set(f"edgeflow:meta:limit:{topic}", size)
            self.ctrl_redis.ltrim(topic, -size, -1)
        except Exception:
            pass

    def queue_size(self, topic: str) -> int:
        """Return list length"""
        self._ensure_connected()
        try:
            return self.ctrl_redis.llen(topic)
        except Exception:
            return 0

    def get_queue_stats(self) -> Dict[str, Dict[str, int]]:
        """Return stats for all tracked topics"""
        self._ensure_connected()
        stats = {}
        try:
            meta_keys = self.ctrl_redis.keys("edgeflow:meta:limit:*")
            
            for key in meta_keys:
                key_str = key.decode('utf-8')
                topic = key_str.replace("edgeflow:meta:limit:", "")
                
                limit_bytes = self.ctrl_redis.get(key)
                limit = int(limit_bytes) if limit_bytes else self.maxlen
                current = self.ctrl_redis.llen(topic)
                
                stats[topic] = {"current": current, "max": limit}
        except Exception as e:
            print(f"DualRedisListBroker Stats Error: {e}")
        return stats

    # ========== Serialization Protocol ==========
    
    def to_config(self) -> dict:
        return {
            "__class_path__": f"{self.__class__.__module__}.{self.__class__.__name__}",
            "ctrl_host": self.ctrl_host,
            "ctrl_port": self.ctrl_port,
            "data_host": self.data_host,
            "data_port": self.data_port,
            "maxlen": self.maxlen
        }
    
    @classmethod
    def from_config(cls, config: dict) -> 'DualRedisListBroker':
        return cls(
            ctrl_host=config.get("ctrl_host"),
            ctrl_port=config.get("ctrl_port"),
            data_host=config.get("data_host"),
            data_port=config.get("data_port"),
            maxlen=config.get("maxlen", 100)
        )
