class PrerequisiteStepError(RuntimeError):
    """Raised when a required previous step has not been run."""

    pass


class DataIntegrityError(ValueError):
    """Raised when data integrity checks fail."""

    pass


class ConditionParsingError(ValueError):
    """Raised when parsing of condition strings fails."""

    pass


class FigureGenerationError(RuntimeError):
    """Raised when there is an error generating figures."""

    pass
