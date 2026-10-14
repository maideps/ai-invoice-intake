"""Who acts on an invoice."""

from dataclasses import dataclass
from enum import Enum

from .errors import InvalidInvoiceDataError


class ActorKind(str, Enum):
    """The platform itself, the AI model, or a person."""

    SYSTEM = "system"
    AI = "ai"
    USER = "user"


@dataclass(frozen=True)
class Actor:
    kind: ActorKind
    name: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidInvoiceDataError("actor name must not be empty")
