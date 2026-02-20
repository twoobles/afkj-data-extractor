"""Custom exception classes for the AFK Journey guild scraper.

All exceptions defined here are fatal — any raise triggers an immediate abort
with a debug screenshot and full traceback.
"""


class OCRConfidenceError(Exception):
    """Raised when PaddleOCR's confidence score is below the configured threshold.

    This indicates the OCR result is unreadable and cannot be trusted.
    Applies to all OCR'd fields including player name regions.

    Args:
        field: The name of the field being OCR'd (e.g. "activity", "rank", "name").
        confidence: The confidence score returned by PaddleOCR.
        threshold: The minimum acceptable confidence threshold.
        raw_text: The raw OCR output, if available.
    """

    def __init__(
        self,
        field: str,
        confidence: float,
        threshold: float,
        raw_text: str = "",
    ) -> None:
        self.field = field
        self.confidence = confidence
        self.threshold = threshold
        self.raw_text = raw_text
        super().__init__(
            f"OCR confidence too low for '{field}': "
            f"expected >= {threshold}, got {confidence}. "
            f"Raw text: '{raw_text}'"
        )


class ParseError(Exception):
    """Raised when OCR succeeds but the result is semantically invalid.

    Examples: Activity value outside 0-1080, stage string that doesn't match
    any known pattern.

    Args:
        field: The name of the field being parsed (e.g. "activity", "stage").
        value: The parsed value that failed validation.
        reason: Human-readable explanation of why the value is invalid.
    """

    def __init__(self, field: str, value: str, reason: str) -> None:
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(
            f"Invalid value for '{field}': '{value}'. {reason}"
        )
