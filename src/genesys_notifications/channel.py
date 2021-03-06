import asyncio
from random import choices
from datetime import datetime, timedelta
from string import ascii_letters, digits
import logging
import websockets
import ujson
from websockets.exceptions import ConnectionClosed, InvalidStatusCode, \
                                  InvalidURI, WebSocketException
from pending import Pending
from .exceptions import ChannelFailure, ConnectionFailure, AuthorizationFailure, \
                        InitializationFailure, LifetimeExtensionFailure, \
                        ReconnectFailure, SubscriptionFailure, RolloverFailure, \
                        ChannelExpiring, ReceiveFailure, RecoveryFailure
from .exceptions import REASON
from .timeouts import TIMEOUT


class Channel:
    "notifications source with error handling, lifetime extension and rollover"

    @property
    def expired(self) -> bool:
        "has the channel exceeded its 24 hour lifetime defined by Genesys"
        return True if datetime.now() >= self._timeouts[TIMEOUT.ChannelExpired].expected else False

    @property
    def connected(self) -> bool:
        return True if self._connection else False


    def __init__(self, uri, topics, lifetime=82800, autoextend=True, reconnect=True, logger=None):
        self._uri = uri
        self._topics = topics
        self._autoextend = autoextend
        self._reconnect = reconnect
        if not logger:
            logging.basicConfig()
            logger = logging.getLogger("channel")
            logger.setLevel(logging.DEBUG)
        self._logger = logger
        self._lifetime = lifetime
        self._heartbeat_timeout = 40
        self._response_timeout = 7
        self._timeouts = Pending()
        self._connection = None
        self._extensions = 0
        self._rollovers = 0

    def __aiter__(self):
        "return the asynchronous iterable"
        return self

    def __await__(self):
        return self.initialize().__await__()


    async def initialize(self):
        "establish websocket connection and subscribe to topics"
        self._timeouts = Pending()
        try:
            await self.connect()
            await self.subscribe()
        except (ConnectionFailure, SubscriptionFailure) as exc:
            raise InitializationFailure(exc.reason, original=exc) from exc
        else:
            self._timeouts.schedule(TIMEOUT.ChannelExpired, self._lifetime)
            self._timeouts.schedule(TIMEOUT.NoHeartbeat, self._heartbeat_timeout)
            self._logger.debug("successfully initialized the channel")


    async def connect(self):
        "open websocket connection"
        try:
            self._connection = await websockets.connect(self._uri, ping_timeout=1, ping_interval=1)
        except InvalidURI as exc:
            raise ConnectionFailure(reason=REASON.InvalidURI, original=exc) from exc
        except InvalidStatusCode as exc:
            if exc.status_code == 401:
                raise AuthorizationFailure(reason=REASON.HTTPUnauthorized, original=exc) from exc
            elif exc.status_code == 403:
                raise AuthorizationFailure(reason=REASON.HTTPForbidden, original=exc) from exc
            else:
                raise ConnectionFailure(reason=REASON.InvalidStatusCode, original=exc) from exc
        except WebSocketException as exc:
            raise ConnectionFailure(reason=REASON.Ambiguous, original=exc) from exc
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
        self._timeouts.schedule(TIMEOUT.NoSubscriptionConfirmation, self._response_timeout)


    async def __anext__(self):
        "asynchronous iterable for getting Notifications Channel JSON messages over websocket"

        notification = None

        # run in a lopp here so that successful recovery can happen transparently from upstream point of view
        while not notification:

            # wait for either data to arrive or expiry getting triggered
            receiver = asyncio.create_task(self._connection.recv())
            timeouthandler = asyncio.create_task(self.handle_timeouts())
            (done, _) = await asyncio.wait((receiver, timeouthandler), return_when=asyncio.FIRST_COMPLETED)
            _.pop().cancel()
            task = done.pop()
            try:
                data = task.result()
            except WebSocketException as exc:
                recovered = await self.handle_websocket_failure(exc)
                if recovered:
                    continue
            # other exceptions are left uncaught, they should bubble up
            else:
                # successful timeout recovery
                if not data:
                    continue
                try:
                    message = ujson.loads(data)
                except ValueError:
                    self.handle_invalid_json(data)
                else:
                    notification = self.process(message)

        # release successfully retrieved message for processing
        return notification


    async def handle_websocket_failure(self, exc):
        self._logger.error("unexpected connection failure: %s", type(exc).__name__)
        if self._reconnect:
            try:
                await self.reconnect()
            except WebSocketException as exc:
                self._logger.error("could not recover from connection failure: %s", type(exc).__name__)
                raise RecoveryFailure(reason=REASON.Ambiguous, original=exc) from exc
            else:
                self._logger.info("successfully recovered from connection failure")
                return True
        else:
            raise ReceiveFailure(reason=REASON.Ambiguous, original=exc) from exc

    def handle_invalid_json(self, data):
        self._logger.debug("invalid data received: %s", data)
        raise ReceiveFailure(reason=REASON.InvalidMessage)


    def process(self, msg):
        "process JSON messages received over websocket from Genesys"

        self._logger.debug(f"received:\n{msg}")

        match msg:

            #  Periodic heartbeat message from Genesys
            case {
                    "topicName": "channel.metadata",
                    "eventBody":{
                        "message":"WebSocket Heartbeat"
                    }
                }:
                self.handle_heartbeat()

            # Failure because
            # 1) channel has already expired
            # 2) channel has been replaced by another due to quota overrun
            # 3) auth token used for the channel has expired
            case {
                    "result": "404",
                    "message": msg
                }:
                self.handle_404(msg)

            # Manual health check response
            case {
                    "topicName": "channel.metadata",
                    "eventBody": {
                        "message": "pong"
                    }
                }:
                self.handle_healthcheck_reply()

            # Genesys is going to close the connection in a minute;
            # raise ChannelExpiring to signal need for rollover
            case {
                    "topicName": "v2.system.socket_closing"
                }:
                self.handle_close_warning()

            # Topic(s) subscription responses
            case {
                    "result": "200",
                    "status": "subscribed"
                }:
                self.handle_subscription_success()

            case {
                    "result": "400",
                    "status": "failure" | "error",
                    "message": msg
                }:
                self.handle_subscription_failure(msg)

            # nothing matched so actual notification data; pass it thru
            case _:
                return msg

    def handle_heartbeat(self):
        self._logger.debug("got heartbeat")
        self._timeouts.reschedule(TIMEOUT.NoHeartbeat)

    def handle_404(self, msg):
        raise ChannelFailure(REASON.Ambiguous, message=msg)

    def handle_healthcheck_reply(self):
        self._logger.info("got health check reply")
        self._timeouts.cancel(TIMEOUT.NoHealthCheckResponse)

    def handle_close_warning(self):
        self._logger.warning("received close warning, rollover required to avoid channel shutdown")
        raise ChannelExpiring(REASON.ChannelClosing)

    def handle_subscription_success(self):
        self._logger.info("topic subscription successful")
        self._timeouts.cancel(TIMEOUT.NoSubscriptionConfirmation)

    def handle_subscription_failure(self, msg):
        raise SubscriptionFailure(REASON.Ambiguous, message=msg)

    async def check(self):
        "send a health check"
        msg = {"message": "ping"}
        await self._connection.send(ujson.dumps(msg))
        self._logger.debug("health check sent")
        self._timeouts.schedule(TIMEOUT.NoHealthCheckResponse, self._response_timeout)

    async def extend(self):
        "extend channel lifetime by resubscribing to the topics"

        try:
            await self.subscribe()
        except SubscriptionFailure as exc:
            raise LifetimeExtensionFailure(exc.reason) from exc
        else:
            self._extensions += 1
            self._timeouts.reschedule(TIMEOUT.ChannelExpired)
            self._logger.debug("successfully extended the channel lifetime (round %i)", self._extensions)
            expiry_at = self._timeouts[TIMEOUT.ChannelExpired].expected.isoformat(" ", timespec="seconds")
            self._logger.info("next managed expiry scheduled at %s", expiry_at)


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
        self._logger.debug("attempting to reconnect the channel")
        try:
            await self.connect()
        except ConnectionFailure as exc:
            self._logger.error("could not reconnect the channel")
            raise ReconnectFailure(exc.reason, original=exc) from exc
        else:
            self._logger.info("successfully re-connected the channel")


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
            self._logger.debug("successfully rolled over to a new URI (round %i)", self._rollovers)


    async def handle_timeouts(self):
        event = await self._timeouts
        match event:
            case TIMEOUT.ChannelExpired:
                await self.handle_ChannelExpired()
            case TIMEOUT.NoHeartbeat:
                await self.handle_NoHeartbeat()
            case TIMEOUT.NoHealthCheckResponse:
                await self.handle_NoHealthCheckResponse()
            case TIMEOUT.NoSubscriptionConfirmation:
                await self.handle_NoSubscriptionConfirmation()


    async def handle_ChannelExpired(self):
        self._logger.warning("managed expiry triggered")
        if self._autoextend:
            await self.extend()
        else:
            raise ChannelExpiring(REASON.ChannelExpired)

    async def handle_NoHeartbeat(self):
        self._logger.error("heartbeat timed out")
        await self.reconnect()

    async def handle_NoHealthCheckResponse(self):
        self._logger.error("health check response timed out")
        await self.reconnect()

    async def handle_NoSubscriptionConfirmation(self):
        self._logger.warning("subscription confirmation timed out")
        await self.reconnect()
        await self.subscribe()
