from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    TRADER = "trader"


class Currency(StrEnum):
    EUR = "EUR"
    USD = "USD"
    CZK = "CZK"


class Incoterm(StrEnum):
    """Incoterms 2020."""

    EXW = "EXW"
    FCA = "FCA"
    CPT = "CPT"
    CIP = "CIP"
    DAP = "DAP"
    DPU = "DPU"
    DDP = "DDP"
    FAS = "FAS"
    FOB = "FOB"
    CFR = "CFR"
    CIF = "CIF"


class OfferStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class DealStatus(StrEnum):
    DRAFT = "DRAFT"
    NEGOTIATION = "NEGOTIATION"
    CONTRACTED = "CONTRACTED"
    SHIPPED = "SHIPPED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
