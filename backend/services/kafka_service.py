"""
Kafka Service - Publishes search events to a Kafka topic.
"""
import os
import json
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError, KafkaError

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from logger_config import logger


class KafkaService:
    def __init__(self):
        self.producer: AIOKafkaProducer | None = None
        self.topic = os.getenv("KAFKA_TOPIC", "person_searches")
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.enabled = os.getenv("KAFKA_ENABLED", "false").lower() == "true"

    async def start(self):
        if not self.enabled:
            logger.info("Kafka is disabled (KAFKA_ENABLED=false). Skipping connection.")
            return
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self.producer.start()
            logger.info(f"✅ Kafka producer connected to {self.bootstrap_servers}")
        except KafkaConnectionError as e:
            logger.error(f"❌ Kafka connection failed: {e}")
            self.producer = None
        except Exception as e:
            logger.error(f"❌ Kafka startup error: {e}")
            self.producer = None

    async def stop(self):
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped.")

    async def publish_search_event(self, name: str):
        if not self.producer:
            return
        event = {
            "event": "person_search",
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self.producer.send_and_wait(self.topic, event)
            logger.debug(f"Kafka event published: {event}")
        except KafkaError as e:
            logger.warning(f"Kafka publish failed: {e}")


kafka_service = KafkaService()
