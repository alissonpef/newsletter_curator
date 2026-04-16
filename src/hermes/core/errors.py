class NewsletterCuratorError(Exception):
    """Base exception for application-specific failures."""


class LlmUnavailableError(NewsletterCuratorError):
    """Raised when LLM services are unavailable or return invalid payloads."""


class ImapFetchError(NewsletterCuratorError):
    """Raised when IMAP retrieval fails."""


class SmtpDeliveryError(NewsletterCuratorError):
    """Raised when SMTP delivery fails."""


class StateLockError(NewsletterCuratorError):
    """Raised when execution state lock cannot be acquired."""


class TtsSynthesisError(NewsletterCuratorError):
    """Raised when TTS synthesis fails."""


class MarketDataUnavailableError(NewsletterCuratorError):
    """Raised when market data providers fail."""
