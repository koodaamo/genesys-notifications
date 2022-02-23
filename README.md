# genesys-notifications client

This is a simple library for accessing genesys websocket notifications.

See https://developer.genesys.cloud/api/rest/v2/notifications/notification_service for background.

The library provides:

* channel topic subscriptions
* channel rollovers when channel expires or times out
* convenient access to notifications
* built-in error handling and recovery

The scope of the library is intentionally limited to making single notifications channel management more convenient by encapsulating the above features.

Additional tasks (possibly) required for production applications include:

* token refresh
* managing multiple channels
* notification response processing
* accounting for the max 20 channels limit
* accounting for the 1000 topics per channel subscription limit
* accounting for the one connection per channel limit

Usage example:

```python3

>>> uri = "wss://streaming.mypurecloud.com/channels/streaming-0-fmtdmf8cdis7jh14udg5p89t6z"
>>> topics = ["v2.analytics.queues.tdmf8cd-k3h43h-udg5p89.observations"]
>>> from genesys_notifications import Channel
>>> async def test(uri, topics):
...    notifications = await Channel(uri, topics)
...    async for n in notifications:
...       print(n)
>>> import asyncio
>>> asyncio.run(test(uri, topics)) 
{
    "topicName": "channel.metadata",
    "eventBody":{
        "message":"WebSocket Heartbeat"
    }
}
```

