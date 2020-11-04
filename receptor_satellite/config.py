def validate(condition, value, default_value, error, logger):
    if condition(value):
        return value
    else:
        if value is not None:
            logger.warning(error)
        return default_value


class Config:
    class Defaults:
        TEXT_UPDATES = False
        TEXT_UPDATE_INTERVAL = 5000
        TEXT_UPDATE_FULL = True

    def __init__(self, text_updates, text_update_interval, text_update_full):
        self.text_updates = text_updates
        self.text_update_interval = (
            text_update_interval // 1000
        )  # Store the interval in seconds
        self.text_update_full = text_update_full

    @classmethod
    def from_raw(cls, raw={}):
        return cls(
            raw["text_updates"], raw["text_update_interval"], raw["text_update_full"]
        )

    @classmethod
    def validate_input(_cls, raw, logger):
        text_updates = raw.get("text_updates")
        text_update_interval = raw.get("text_update_interval")
        text_update_full = raw.get("text_update_full")

        validated = {}
        validated["text_updates"] = validate(
            lambda val: type(val) == bool,
            text_updates,
            Config.Defaults.TEXT_UPDATES,
            f"Expected the value of text_updates '{text_updates}' to be a boolean",
            logger,
        )
        validated["text_update_full"] = validate(
            lambda val: type(val) == bool,
            text_update_full,
            Config.Defaults.TEXT_UPDATE_FULL,
            f"Expected the value of text_update_full '{text_update_full}' to be a boolean",
            logger,
        )
        validated["text_update_interval"] = validate(
            lambda val: type(val) == int and val >= 5000,
            text_update_interval,
            Config.Defaults.TEXT_UPDATE_INTERVAL,
            f"Expected the value of text_update_interval '{text_update_interval}' to be an integer greater or equal than 5000",
            logger,
        )
        return validated
