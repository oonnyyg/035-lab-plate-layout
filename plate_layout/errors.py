"""Domain error type for plate layout planning."""


class LayoutError(ValueError):
    """Raised when input data or configuration is invalid.

    Messages are user-facing and pinpoint the offending record, field or
    well so experimenters can correct the source file.
    """
