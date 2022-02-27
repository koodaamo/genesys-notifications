from enum import Enum


class REASON(Enum):
    ConnectionClosed = 1 # see websockets error referenc
    InvalidHandshake = 2 # see websockets error reference
    InvalidURI = 3 # see websockets error reference
    PayloadTooBig = 4 # see websockets error reference
    ProtocolFailure = 5 # see websockets error reference
    TokenExpired = 6 # Genesys token used to create the channel has expired
    ChannelExpired = 7 # 24 hrs has passed since channel creation
    ChannelClosing = 8 # Genesys is closing the channel in one minute
    Ambiguous = 9 # Unknown or ambiguous


class ChannelException(Exception):
    ""

class ChannelExpiring(ChannelException):
    "Channel is expiring because of end of life or ad-hoc close"


# Failures that should be caught

class ChannelFailure(ChannelException):
    "Notifications channel operation failed"

    def __init__(self, reason: REASON):
        self.reason = reason

    def __str__(self):
        return self.__doc__


# Initialization failure exceptions

class InitializationFailure(ChannelFailure):
    "Websocket connection or topic subscription failed"

class ConnectionFailure(InitializationFailure):
    "Could not open websocket channel connection"

class SubscriptionFailure(InitializationFailure):
    "Could not subscribe to notification topic(s)"


# Notification reception failure  exceptions

class ReceiveFailure(ChannelFailure):
    "Failure to receive data while listening on open channel"


# Channel recovery failure exceptions

class RecoveryFailure(ChannelFailure):
    "Could not recover from channel failure"

class LifetimeExtensionFailure(RecoveryFailure):
    "Could not prevent impending channel close by resubscribing to topics"

class ReconnectFailure(RecoveryFailure):
    "Could not re-connect to the channel"

class RolloverFailure(RecoveryFailure):
    "Could not connect or resubscribe topics using the new URI"