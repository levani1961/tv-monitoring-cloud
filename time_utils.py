from datetime import timedelta


def seconds_to_hhmmss(seconds):
    seconds = max(0, int(seconds))
    return str(timedelta(seconds=seconds))


def hour_to_seconds(hour_value):
    return int(hour_value) * 3600


def seconds_to_filename_time(seconds):
    return seconds_to_hhmmss(seconds).replace(":", "-")


def add_seconds_to_datetime(value, seconds):
    return value + timedelta(seconds=int(seconds))
