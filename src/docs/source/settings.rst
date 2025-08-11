Required Settings
=================

Set these settings in your Django project's ``settings.py``, preferably retrieved from environment variables:

.. code:: python

    # settings.py

    import os
    from pathlib import Path

    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_PINPOINT_POOL_ARN = os.getenv("AWS_PINPOINT_POOL_ARN")
    AWS_PINPOINT_MAX_PRICE_VOICE = os.getenv("AWS_PINPOINT_MAX_PRICE_VOICE")
    AWS_PINPOINT_MAX_PRICE_SMS = os.getenv("AWS_PINPOINT_MAX_PRICE_SMS")
    WIALON_TOKEN = os.getenv("WIALON_TOKEN")

    # rest of the settings
    ...


Reference
---------

+------------------------------+--------------------------------------------------+
| Name                         | Description                                      |
+==============================+==================================================+
| AWS_ACCESS_KEY_ID            | An AWS access key id.                            |
+------------------------------+--------------------------------------------------+
| AWS_SECRET_ACCESS_KEY        | An AWS secret access key.                        |
+------------------------------+--------------------------------------------------+
| AWS_PINPOINT_POOL_ARN        | An AWS pinpoint phone pool ARN.                  |
+------------------------------+--------------------------------------------------+
| AWS_PINPOINT_MAX_PRICE_VOICE | Max price-per-minute for pinpoint voice calls.   |
+------------------------------+--------------------------------------------------+
| AWS_PINPOINT_MAX_PRICE_SMS   | Max price-per-message for pinpoint sms messages. |
+------------------------------+--------------------------------------------------+
| WIALON_TOKEN                 | An active Wialon API token.                      |
+------------------------------+--------------------------------------------------+

Security Policy
---------------

Recommended security policy:

.. code:: json

   {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "sms-voice:DescribePool",
                    "sms-voice:ListPools",
                    "sms-voice:SendTextMessage"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "sms-voice:CreatePool",
                    "sms-voice:UpdatePool",
                    "sms-voice:DeletePool"
                ],
                "Resource": "arn:aws:sms-voice:*:<ACCOUNT_ID>:pool/*",
                "Condition": {
                    "StringEquals": {
                        "aws:RequestedRegion": ["<REGION_0>", "<REGION_1>"]
                    }
                }
            }
        ]
    }

