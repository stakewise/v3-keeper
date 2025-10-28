class Singleton(type):
    _instances: dict = {}

    def __call__(cls, *args, **kwargs):  # type: ignore
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class AppState(metaclass=Singleton):
    def __init__(self) -> None:
        self.last_price_updated_timestamp: int | None = None
        self.force_exits_updated_timestamp: int | None = None
        self.ltv_updated_timestamp: int | None = None
