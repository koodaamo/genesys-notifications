from enum import Enum


class TIMEOUT(Enum):
    ChannelExpired = 1 # Genesys closes the connection after 24 hours
    NoHeartbeat = 2 # Genesys normally sends heartbeats every 30 seconds
    NoHealthCheckResponse = 3 # Manual healthcheck received no response
    NoSubscriptionConfirmation = 4 # Channel topic subscription was not confirmed