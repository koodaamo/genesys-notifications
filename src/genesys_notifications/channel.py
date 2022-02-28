from random import choices
from datetime import datetime, timedelta
from string import ascii_letters, digits
import logging
import websockets
import ujson
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, \
                                  ConnectionClosedOK, InvalidHandshake
from .exceptions import ChannelFailure, ConnectionFailure, InitializationFailure, \
                        LifetimeExtensionFailure, ReconnectFailure, \
                        SubscriptionFailure, RolloverFailure, ChannelExpiring
from .exceptions import REASON


class Channel:
    "notifications source with error handling, lifetime extension and rollover"

    @property
    def expired(self) -> bool:
        "has the channel exceeded its 24 hour lifetime defined by Genesys"
        return True if datetime.now() >= self._expiration else False

    @property
    def connected(self) -> bool:
        return True if self._connection else False


    def __init__(self, uri, topics, extend=True, rollover=23, logger=None):
        self._uri = uri
        self._topics = topics
        self._extend = extend
        if not logger:
            logging.basicConfig()
            logger = logging.getLogger("channel")
            logger.setLevel(logging.DEBUG)
        self._logger = logger
        self._rollover = 23
        self._expiration = datetime.now() + timedelta(hours=rollover)
        self._connection = None
        self._extensions = 0
        self._rollovers = 0
        self._status = {
            "expiration": self._expiration,
            "extensions": self._extensions,
            "rollovers": self._rollovers
        }

    def __aiter__(self):
        "return the asynchronous iterable"
        return self

    def __await__(self):
        return self.initialize().__await__()

    async def __anext__(self):
        "asynchronous iterable implementation"

        # Initialize if not connected, roll over
        # if expired or error occurs, stop if
        # we are already closed.

        if not self.connected:
            await self.connect()

        if self.expired:
            raise ChannelExpiring(REASON.ChannelExpired)

        message = None

        while not message:
            try:
                data = await self._connection.recv()
            except ConnectionClosedOK:
                raise StopAsyncIteration
            except ConnectionClosedError: # raised also when pingpong times out
                await self.reconnect()
                continue
            else:
                if data:
                    try:
                        message = ujson.loads(data)
                    except ValueError:
                        self._logger.error("non-JSON data received: ", data)

        await self.process(message)


    async def process(self, msg):
        "handle subscription & healtcheck confirmation, failure and close messages"

        self._logger.debug(f"received:\n{msg}")

        match msg:

            #  Periodic heartbeat message from Genesys
            case {
                    "topicName": "channel.metadata",
                    "eventBody":{
                        "message":"WebSocket Heartbeat"
                    }
                }:
                self._logger.debug("got heartbeat")

            # Failure because
            # 1) channel has already expired
            # 2) channel has been replaced by another due to quota overrun
            # 3) auth token used for the channel has expired
            case {
                    "result": "404"
                }:
                raise ChannelFailure(REASON.Ambiguous)

            # Manual health check response
            case {
                    "topicName": "channel.metadata",
                    "eventBody": {
                        "message": "pong"
                    }
                }:
                self._logger.info("got health check reply")

            # Genesys is going to close the channel in a minute;
            # try to extend it or raise ChannelExpiring for manual
            # handling
            case {
                "topicName": "v2.system.socket_closing"
                }:
                self._logger.warning("received close warning, extension or rollover required")
                if self._extend:
                    await self.extend()
                else:
                    raise ChannelExpiring(REASON.ChannelClosing)

            # Topic(s) subscription responses
            case  {
                    "result": "200",
                    "status": "subscribed"
                }:
                self._logger.info("subscription successful")

            case  {
                    "result": "400",
                    "status": "failure"
                }:
                raise SubscriptionFailure(REASON.Ambiguous)

            case  {
                    "result": "400",
                    "status": "error"
                }:
                raise SubscriptionFailure(REASON.Ambiguous)

    async def connect(self):
        "open websocket connection"
        try:
            self._connection = await websockets.connect(self._uri, ping_timeout=1, ping_interval=1)
        except InvalidHandshake as exc:
            raise ConnectionFailure(reason=REASON.InvalidHandshake) from exc
        else:
            self._logger.info("connected")


    async def subscribe(self):
        "subscribe to topics"
        if not self.connected:
            raise SubscriptionFailure(REASON.ConnectionClosed)
        correlation_id = ''.join(choices(ascii_letters + digits, k=16))
        subscription = {
            "message":"subscribe",
            "topics": self._topics,
            "correlationId": correlation_id
        }
        self._logger.debug(f"sending:\n{subscription}")
        await self._connection.send(ujson.dumps(subscription))


    async def initialize(self):
        "establish websocket connection and subscribe to topics"
        try:
            await self.connect()
            await self.subscribe()
        except (ConnectionFailure, SubscriptionFailure) as exc:
            raise InitializationFailure(exc.reason) from exc
        else:
            self._logger.debug("successfully initialized the channel")


    async def extend(self):
        "extend channel lifetime by resubscribing to the topics"

        try:
            await self.subscribe()
        except SubscriptionFailure as exc:
            raise LifetimeExtensionFailure(exc.reason) from exc
        else:
            self._extensions += 1
            self._expiration = datetime.now() + timedelta(hours=23)
            self._logger.debug("successfully extended the channel lifetime")


    async def close(self):
        "close the websocket connection"
        self._logger.warning("attempting to close the channel now")
        try:
            await self._connection.close()
        except ConnectionClosed:
            pass
        self._connection = None
        self._logger.warning("notification channel is now closed")


    async def reconnect(self):
        "re-establish websocket connection"
        try:
            await self.close()
        except ConnectionClosed:
            pass
        try:
            await self.connect()
        except ConnectionFailure as exc:
            raise ReconnectFailure(exc.reason) from exc
        else:
            self._logger.debug("successfully re-connected the channel")


    async def rollover(self, uri):
        "re-establish a new connection to a new URI with same subscriptions"

        # keep ref to old connection for closing
        self._old_connection = self._connection

        # attempt to open the new uri
        self._uri = uri
        try:
            await self.initialize()
        except InitializationFailure as exc:
            raise RolloverFailure(exc.reason) from exc
        else:
            try:
                await self._old_connection.close()
            except ConnectionClosed:
                pass
            self._rollovers += 1
            del self._old_connection
            self._logger.debug("successfully rolled over to a new URI")
