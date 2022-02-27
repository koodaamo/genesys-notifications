import asyncio
from unittest.mock import AsyncMock, patch
import json
import pytest
from pytest import mark


class MockConnection:

    _action = None
    _correlationID = None

    async def send(self, msg):
        msg = json.loads(msg)

        if msg["message"] == "subscribe":
            self._action = "subscribe"

        if cid := msg.get("correlationId"):
            self._correlationID = cid
    
    async def recv(self):
        response = {}

        if self._correlationID:
            response["correlationId"] = self._correlationID

        if self._action == "subscribe":
            response["status"] = "subscribed"

        return json.dumps(response)



@mark.asyncio
async def test_connection_awaiting():
    from genesys_notifications import Channel
    import websockets
    websockets.connect = AsyncMock(return_value = MockConnection())
    channel = Channel("wss://test", ["test_topic1", "test_topic2"])

    await channel.connect()
    websockets.connect.assert_awaited()
    assert isinstance(channel._connection, MockConnection)

    await channel.subscribe()
