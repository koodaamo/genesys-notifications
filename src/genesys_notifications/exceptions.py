from enum import Enum

# Exception reason codes; see the websockets library error 
# reference and Genesys notification system docs.

class REASON(Enum):
    ConnectionClosed = 1
    InvalidHandshake = 2
    InvalidURI = 3
    PayloadTooBig = 4
    ProtocolFailure = 5
    TokenExpired = 6 # Genesys token used to create the channel has expired
    ChannelExpired = 7 # 24 hrs has passed since Genesys channel creation
    ChannelClosing = 8 # Genesys is closing the channel in one minute
    Ambiguous = 9 # Unknown or ambiguous reason


class ChannelException(Exception):
    "The base exception for subclassing"

    def __init__(self, reason: REASON, message=None):
        self.reason = reason
        self.message = message

    def __str__(self):
        return self.__doc__


# Channel expiry

class ChannelExpiring(ChannelException):
    "Channel is expiring because of end of life or ad-hoc close"


# Channel failures

class ChannelFailure(ChannelException):
    "Base exception for notifications channel failures"


# Channel initialization failures

class InitializationFailure(ChannelFailure):
    "Websocket connection or topic subscription failed"

class ConnectionFailure(InitializationFailure):
    "Could not open websocket channel connection"

class SubscriptionFailure(InitializationFailure):
    "Could not subscribe to notification topic(s)"


# Channel notification reception failures

class ReceiveFailure(ChannelFailure):
    "Failure to receive data while listening on open channel"


# Channel recovery failures

class RecoveryFailure(ChannelFailure):
    "Could not recover from channel failure"

class LifetimeExtensionFailure(RecoveryFailure):
    "Could not prevent impending channel close by resubscribing to topics"

class ReconnectFailure(RecoveryFailure):
    "Could not re-connect to the channel"

class RolloverFailure(RecoveryFailure):
    "Could not connect or resubscribe topics using the new URI"