"""AI assistant processing errors (provider / quota)."""


class WhisperProcessingError(Exception):
    pass


class GeminiProcessingError(Exception):
    pass


class QuotaExhaustedError(Exception):
    def __init__(self, service: str) -> None:
        self.service = service
        super().__init__(service)
