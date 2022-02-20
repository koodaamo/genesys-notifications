from random import choices
from datetime import datetime, timedelta
from string import ascii_letters, digits
import asyncio
import logging
import websockets
import ujson
from websockets.exceptions import ConnectionClosed, ConnectionClosedError


class Channel:

    def __init__(self, uri, topics, logger=None):
        self._uri = uri
        self._topics = topics
        if not logger:
            logging.basicConfig()
            logger = logging.getLogger(f"channel {uri}")
            logger.setLevel(logging.DEBUG)
        self._logger = logger
        self._expiry = datetime.now() + timedelta(hours=23)
        self._connection = None

    def __aiter__(self):
        "return the asynchronous iterable"
        return self

    def __await__(self):
        return self.initialize().__await__()
        
    async def __anext__(self):
        "asynchronous iterable implementation"
        if not self._connection:
            raise Exception("not connected")
        if datetime.now() >= self._expiry:
            await self.initialize()
        try:
            msg = await self._connection.recv()
        except (ConnectionClosed, ConnectionClosedError):
            await self.initialize()
            data = await self.__anext__()
        else:
            data = ujson.loads(msg)
            if data["topicName"] == "v2.system.socket_closing":
                self._logger.debug("received close notification")
                await self.initialize()
                data = await self.__anext__()
                self._logger.info("rolled over due to close notification")
        finally:
            return data

    async def connect(self):
        self._connection = await websockets.connect(self._uri)
        self._logger.info(f"connected {self._uri}")

    async def subscribe(self):
        if not self._connection:
            raise Exception("not connected")
        correlation_id = ''.join(choices(ascii_letters + digits, k=16))
        subscription = {
            "message":"subscribe",
            "topics": self._topics,
            "correlationId": correlation_id
        }
        await self._connection.send(ujson.dumps(subscription))
        response = await self._connection.recv()
        data = ujson.loads(response)
        if data["correlationId"] == correlation_id:
            if data["status"] != "subscribed":
                raise Exception("could not subscribe to topics!")

    async def close(self):
        if not self._connection:
            raise Exception("not connected")
        await self._connection.close()
        self._connection = None

    async def initialize(self):
        await self.connect()
        await self.subscribe()
        self._logger.debug("successfully initialized the channel")

