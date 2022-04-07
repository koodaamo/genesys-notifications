# genesys-notifications client

This is a simple library for receiving genesys websocket notifications.

See https://developer.genesys.cloud/api/rest/v2/notifications/notification_service for background.

The library provides a notifications Channel implementation that encapsulates the websocket
connection management. Features:

* channel connection & topic subscriptions
* async iterator for getting notifications
* automatic channel reconnect on failure
* helpful custom exceptions
* automatic channel lifetime extension to avoid channel expiry
* support for rollover to a new connection when channel expires or closes for maintenance [^1]

The scope of the library is intentionally limited to making single notifications channel management more convenient by encapsulating the above features.

It does **not**:

* refresh the access token
* manage multiple channels[^2].
* process received topic notifications[^3]
* account for the max 20 channels limit
* account for the 1000 topics per channel subscription limit
* account for the one connection per channel limit

Usage:

First create the Genesys channel as instructed by the Genesys docs. Then:

1. Import and instantiate a Channel, passing in URI and topics.
1. Await the channel to connect and subscribe.
1. Iterate over the result to receive notifications.

Example:

```python

>>> uri = "wss://streaming.mypurecloud.com/channels/streaming-0-fmtdmf8cdis7jh14udg5p89t6z"
>>> topics = ["v2.analytics.queues.tdmf8cd-k3h43h-udg5p89.observations"]
>>> from genesys_notifications import Channel
>>> from genesys_notifications.exceptions import InitializationFailure, RecoveryFailure
>>> async def test(uri, topics):
...    try:
...       notifications = await Channel(uri, topics)
...    except InitializationFailure:
...       # Handle websocket connection opening and topic subscription failures;
...       # ConnectionFailure and SubscriptionFailure can be caught separately as well.
...    try:
...       async for n in notifications:
...    except RecoveryFailure:
...       # Handle cases when the channel is not able to automatically recover from issues:
...       # in case of problems, it will try once to reconnect & resubscibe before giving up, and
...       # in case of scheduled expiry or ad-hoc Genesys-side close notification, it will try to
          # extend its lifetime by resubscribing to topics.
...    else:
...       print(n)
>>>
>>> import asyncio
>>> asyncio.run(test(uri, topics)) 
{
    "topicName": "channel.metadata",
    "eventBody":{
        "message":"WebSocket Heartbeat"
    }
}
```

See the `exceptions` module for all the available exceptions. The reason for exception is always available in its `reason` attribute. See `exceptions.REASON` enum for possible reasons.

[^1]: Instantiate the Channel with `extend=False` to disable automatic lifetime extension & handle it manually by catching `ChannelExpiring`
[^2]: Except when `channel.rollover(uri)` is called; under the hood, a new websocket connection is then initialized and transparently replaces the original
[^3]: Except for the bare minimum required to support the provided features; subscription confirmations, channel close notifications etc.
