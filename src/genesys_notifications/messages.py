from enum import Enum


class MESSAGE(Enum):
    "Genesys messages that can be handled"


    # Channel not found by Genesys because it was idle for 24 hours and was closed,
    # channel was replaced by an over-the-quota, new channel, or the authorization
    # token expired
    CHANNELFAILURE = {
        "result": "404"
    }

    # Genesys autogenerated periodic heartbeat message
    HEARTBEAT = {
        "topicName": "channel.metadata",
        "eventBody":{
            "message":"WebSocket Heartbeat"
        }
    }

    # Genesys response on successful notification topic(s) subscription
    SUBSCRIBED = {
        "result": "200",
        "status": "subscribed"
    }

    # Genesys response on failed subscription
    SUBSCRIBEFAILURE = {
        "result": "400",
        "status": "failed"
    }

    SUBSCRIBEERROR = {
        "result": "400",
        "status": "error"
    }

    #{'correlationId': 'uno5VlaUHt5t2Mul', 'topics': [], 'result': '400', 'status': 'error', 'message': 'Required data missing from subscribe request.'}

    # Genesys response on manual health check
    HEALTHOK = {
        "topicName": "channel.metadata",
        "eventBody": {
            "message": "pong"
        }
    }

    # Genesys close warning one minute in advance
    CLOSING = {
        "topicName": "v2.system.socket_closing"
    }

