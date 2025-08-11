Usage
=====

To send a notification, send a GET request to ``/notify/<str:notification_method>/``.

Allowed notification methods
----------------------------

    - ``sms``: Sends the message via SMS to target phone numbers.
    - ``voice``: Sends the message via voice to target phone numbers.

Query parameters
----------------

    - ``unit_id``: A Wialon unit id to retrieve phone numbers for.
    - ``message``: A message to dispatch to the phone numbers.
    - ``dry_run``: Whether or not to perform the notification dispatch as a dry run (no messages sent to phones).

Response codes
--------------

    - ``406``: Invalid unit id, message or method.
    - ``200``: Notifications successfully dispatched OR unit had no phones.
