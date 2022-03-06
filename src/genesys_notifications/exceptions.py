from enum import Enum

# Exception reason codes; see the websockets library error
# reference and Genesys notification system docs.
# Reason hierarchy is indicated by number of digits when applicable,
# e.g. InvalidHandshake -> InvalidStatusCode -> HTTPUnauthorized.

class REASON(Enum):
    ConnectionClosed = 1 # as defined in websockets
    InvalidHandshake = 2 # as defined in websockets
    InvalidStatusCode = 21 # as defined in websockets
    HTTPUnauthorized = 211
    HTTPForbidden = 212
    InvalidURI = 3 # as defined in websockets
    InvalidMessage = 4 # could not parse JSON
    ChannelExpired = 5 # 24 hrs has passed since Genesys channel creation
    ChannelClosing = 6 # Genesys is closing the channel in one minute
    Ambiguous = 7 # Unknown or ambiguous reason


class ChannelException(Exception):
    "The base exception for subclassing"

    def __init__(self, reason: REASON, message=None, original=None):
        self.reason = reason
        self.message = message
        self.original = original

    def __str__(self):
        return "%s: %s: %s" % (self.__class__.__name__, self.__doc__, self.reason.name)


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

class AuthorizationFailure(ConnectionFailure):
    "Connection was rejected"

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
