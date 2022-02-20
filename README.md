# genesys-notifications client

This is a simple library for accessing genesys websocket notifications.

See https://developer.genesys.cloud/api/rest/v2/notifications/notification_service .

The library provides:

* channel topic subscriptions
* channel rollovers when channel expires or times out
* convenient access to notifications

Usage:

```python3

>>> uri = "wss://<your ws uri here>"
>>> topics = [<your topics here>]
>>> from genesys_notifications import Channel
>>> notifications = await Channel(uri, topics)
>>> async for n in notifications
...    print(n)
{
    "topicName": "channel.metadata",
    "eventBody":{
        "message":"WebSocket Heartbeat"
    }
}
```

