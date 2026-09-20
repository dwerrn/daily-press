class CollectorError(RuntimeError):
    """A failure isolated to a single external content collector."""

    def __init__(self, collector: str, message: str) -> None:
        super().__init__(f"{collector} collector failed: {message}")
        self.collector = collector
