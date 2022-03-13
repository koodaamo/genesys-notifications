1.3 (2022-03-13)
-----------------

- Optionally attempt a simple reconnect on connection failure once
- Behavior change: don't stop on unexpected connection close; instead raise
  ReceiveFailure or attempt simple reconnect if enabled
- Better failure logging

1.2 (2022-03-11)
-----------------

- Behavior change: do not try to autoextend when Genesys sends ad-hoc
  close warning; autoextend by topic resubscribe works for 24 hr lifetime
  expiry only

1.1 (2022-03-10)
-----------------

- Improve managed expiry
- Rename Channel init params: 'rollover' is now 'lifetime' and 'extend'
  is 'autoextend'
- Improve logging


1.0 (2022-03-08)
-----------------

- Initial release
