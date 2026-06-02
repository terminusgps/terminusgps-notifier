from authorizenet import apicontractsv1
from django.utils.translation import gettext_lazy as _

__all__ = [
    "HOSTED_PAYMENT_PAGE_SETTINGS",
    "HOSTED_PROFILE_PAGE_SETTINGS",
    "SUBSCRIPTION_NOT_FOUND",
    "TIMEZONES",
]

SUBSCRIPTION_NOT_FOUND = "E00035"

HOSTED_PROFILE_PAGE_SETTINGS_LIST = [
    apicontractsv1.settingType(
        settingName=apicontractsv1.settingNameEnum.hostedProfileSaveButtonText,
        settingValue="Save",
    ),
    apicontractsv1.settingType(
        settingName=apicontractsv1.settingNameEnum.hostedProfileReturnUrl,
        settingValue="https://localhost:8000/dashboard/",
    ),
    apicontractsv1.settingType(
        settingName=apicontractsv1.settingNameEnum.hostedProfileReturnUrlText,
        settingValue="Go Back",
    ),
    apicontractsv1.settingType(
        settingName=apicontractsv1.settingNameEnum.hostedProfilePageBorderVisible,
        settingValue="true",
    ),
    apicontractsv1.settingType(
        settingName=apicontractsv1.settingNameEnum.hostedProfileHeadingBgColor,
        settingValue="#ffc7b6",
    ),
    # apicontractsv1.settingType(
    #     settingName=apicontractsv1.settingNameEnum.hostedProfilePaymentOptions,
    #     settingValue="showAll",
    # ),
    # apicontractsv1.settingType(
    #     settingName=apicontractsv1.settingNameEnum.hostedProfileValidationMode,
    #     settingValue="liveMode",
    # ),
    # apicontractsv1.settingType(
    #     settingName=apicontractsv1.settingNameEnum.hostedProfileBillingAddressRequired,
    #     settingValue="false",
    # ),
    # apicontractsv1.settingType(
    #     settingName=apicontractsv1.settingNameEnum.hostedProfileCardCodeRequired,
    #     settingValue="true",
    # ),
    # apicontractsv1.settingType(
    #     settingName=apicontractsv1.settingNameEnum.hostedProfileBillingAddressOptions,
    #     settingValue="showBillingAddress",
    # ),
    # apicontractsv1.settingType(
    #     settingName=apicontractsv1.settingNameEnum.hostedProfileManageOptions,
    #     settingValue="showAll",
    # ),
]

HOSTED_PAYMENT_PAGE_SETTINGS_LIST = [
    apicontractsv1.settingType(
        settingName=apicontractsv1.settingNameEnum.hostedPaymentReturnOptions,
        settingValue='{"showReceipt": true, "url": "https://api.terminusgps.com/dashboard/", "urlText": "Continue", "cancelUrl": "https://api.terminusgps.com/dashboard/", "cancelUrlText": "Cancel"}',
    ),
    # apicontractsv1.settingType(
    #     settingName=apicontractsv1.settingNameEnum.hostedPaymentButtonOptions,
    #     settingValue='{"text": "Pay"}',
    # ),
    # apicontractsv1.settingType(
    #     settingName=apicontractsv1.settingNameEnum.hostedPaymentStyleOptions,
    #     settingValue='{"bgColor": "red"}',
    # ),
    # apicontractsv1.settingType(
    #     settingName=apicontractsv1.settingNameEnum.hostedPaymentPaymentOptions,
    #     settingValue='{"cardCodeRequired": true, "showCreditCard": true, "showBankAccount": true, "customerProfileId": false}',
    # ),
    apicontractsv1.settingType(
        settingName=apicontractsv1.settingNameEnum.hostedPaymentSecurityOptions,
        settingValue='{"captcha": true}',
    ),
    # apicontractsv1.settingType(
    #     settingName=apicontractsv1.settingNameEnum.hostedPaymentShippingAddressOptions,
    #     settingValue='{"show": true, "required": true}',
    # ),
    # apicontractsv1.settingType(
    #     settingName=apicontractsv1.settingNameEnum.hostedPaymentBillingAddressOptions,
    #     settingValue='{"show": true, "required": false}',
    # ),
    # apicontractsv1.settingType(
    #     settingName=apicontractsv1.settingNameEnum.hostedPaymentCustomerOptions,
    #     settingValue='{"showEmail": false, "requiredEmail": false, "addPaymentProfile": true}',
    # ),
    apicontractsv1.settingType(
        settingName=apicontractsv1.settingNameEnum.hostedPaymentOrderOptions,
        settingValue='{"show": true, "merchantName": "Terminus GPS"}',
    ),
]

HOSTED_PROFILE_PAGE_SETTINGS = apicontractsv1.ArrayOfSetting()
for setting in HOSTED_PROFILE_PAGE_SETTINGS_LIST:
    HOSTED_PROFILE_PAGE_SETTINGS.setting.append(setting)

HOSTED_PAYMENT_PAGE_SETTINGS = apicontractsv1.ArrayOfSetting()
for setting in HOSTED_PAYMENT_PAGE_SETTINGS_LIST:
    HOSTED_PAYMENT_PAGE_SETTINGS.setting.append(setting)


TIMEZONES = [
    (-43200, _("International Date Line West")),
    (-39600, _("Midway Island, Samoa")),
    (-36000, _("Hawaii")),
    (-34200, _("French Polynesia, Marquesas Islands")),
    (-32400, _("Alaska")),
    (-28800, _("Pacific Time (US & Canada)")),
    (-25200, _("Mountain Time (US & Canada)")),
    (-21600, _("Central Time (US & Canada), Guadalajara, Mexico City")),
    (-18000, _("Eastern time (US & Canada)")),
    (-16200, _("Not used for Venezuela")),
    (-14400, _("Atlantic time (Canada), Manaus, Santiago, Venezuela")),
    (-12600, _("Newfoundland")),
    (-10800, _("Greenland, Brasilia, Montevideo")),
    (-7200, _("Mid-Atlantic")),
    (-3600, _("Azores")),
    (0, _("GMT: Dublin, Edinburgh, Lisbon, London")),
    (3600, _("Amsterdam, Berlin, Rome, Vienna, Prague, Brussels")),
    (7200, _("Athens, Istanbul, Beirut, Cairo, Jerusalem, Kaliningrad")),
    (10800, _("Minsk, Nairobi, Moscow, Baghdad")),
    (12600, _("Iran")),
    (14400, _("Baku, Yerevan, Izhevsk, Samara")),
    (16200, _("Afghanistan")),
    (18000, _("Astana, Ekaterinburg, Tashkent")),
    (19800, _("Chennai, Kolkata, Mumbai, New Delhi")),
    (20700, _("Nepal")),
    (21600, _("Dhaka, Omsk")),
    (23400, _("Myanmar, Cocos Islands")),
    (25200, _("Bangkok, Hanoi, Jakarta, Krasnoyarsk, Kemerovo, Novosibirsk")),
    (28800, _("Ulaanbaatar, Perth, Irkutsk, Chita, Kuala Lumpur")),
    (32400, _("Japan Standard Time, Yakutsk")),
    (34200, _("Australian Central Standard Time")),
    (36000, _("Canberra, Melbourne, Sydney, Hobart, Vladivostok, Magadan")),
    (37800, _("Lord Howe Standard Time")),
    (39600, _("Solomon Is., New Caledonia, Chokurdakh, Sakhalin")),
    (43200, _("Auckland, Wellington, Anadyr, Petropavlovsk-Kamchatsky")),
    (45900, _("New Zealand, Chatham Island")),
    (46800, _("Nuku'alofa")),
    (50400, _("Kiribati, Line Islands")),
]
