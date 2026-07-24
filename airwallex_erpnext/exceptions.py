class AirwallexError(Exception):
    """Base integration error."""


class AirwallexAuthenticationError(AirwallexError):
    pass


class AirwallexPermissionError(AirwallexError):
    pass


class AirwallexRateLimitError(AirwallexError):
    pass


class AirwallexAPIError(AirwallexError):
    pass


class MappingRequiredError(AirwallexError):
    pass


class ConflictDetectedError(AirwallexError):
    pass


class SignatureVerificationError(AirwallexError):
    pass
