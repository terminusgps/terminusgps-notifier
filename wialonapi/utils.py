def clean_phone_numbers(phone_numbers: list[str]) -> list[str]:
    for old_phone in phone_numbers:
        if "," in old_phone:
            new_phone = old_phone.split(",")
            phone_numbers.remove(old_phone)
            phone_numbers.extend(new_phone)
    return phone_numbers
