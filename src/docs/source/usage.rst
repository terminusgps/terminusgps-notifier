Usage
=====

To send a notification, send a GET request to ``/notify/<str:method>/``.

All query parameters are required.

Allowed methods
---------------

    - ``sms``: Sends the message via SMS to target phone numbers.
    - ``call``: Sends the message via voice to target phone numbers.
    - ``phone``: Sends the message via voice to target phone numbers.
    - ``voice``: Sends the message via voice to target phone numbers.

Query parameters
----------------

    - ``unit_id``: A Wialon unit id to retrieve phone numbers for.
    - ``message``: A message to dispatch to the phone numbers.

Response codes
--------------

    - ``406``: Invalid unit id, message or method OR unit has no phone numbers.
    - ``200``: Notifications successfully dispatched.
