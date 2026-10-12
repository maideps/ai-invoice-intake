"""Fictional vendors, customers and the wording each language uses on an invoice.

Every name here is invented. Each vendor fixes the currency, tax rate, language, date and
number format, so the samples differ the way real invoices from different countries do.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Unit = Literal["pc", "h", "month"]


@dataclass(frozen=True)
class Language:
    labels: dict[str, str]
    payment_terms: str  # formatted with {days}


@dataclass(frozen=True)
class NumberStyle:
    decimal_sep: str
    group_sep: str


@dataclass(frozen=True)
class Item:
    description: str
    unit: Unit
    min_price: Decimal
    max_price: Decimal


@dataclass(frozen=True)
class Vendor:
    key: str
    name: str
    address: tuple[str, ...]
    currency: str
    currency_symbol: str
    symbol_after: bool
    tax_label: str
    tax_rate: Decimal
    language: Language
    numbers: NumberStyle
    date_format: str
    number_pattern: str  # formatted with {year} and {n}
    page_size: Literal["A4", "LETTER"]
    payment_days: int
    items: tuple[Item, ...]


@dataclass(frozen=True)
class Customer:
    name: str
    address: tuple[str, ...]


def _items(unit: Unit, *rows: tuple[str, str, str]) -> tuple[Item, ...]:
    return tuple(Item(desc, unit, Decimal(low), Decimal(high)) for desc, low, high in rows)


ENGLISH = Language(
    labels={
        "title": "INVOICE",
        "number": "Invoice no.",
        "date": "Invoice date",
        "due": "Due date",
        "bill_to": "Bill to",
        "description": "Description",
        "quantity": "Qty",
        "unit_price": "Unit price",
        "amount": "Amount",
        "subtotal": "Subtotal",
        "total": "Total due",
    },
    payment_terms="Payment terms: net {days} days",
)
GERMAN = Language(
    labels={
        "title": "RECHNUNG",
        "number": "Rechnungsnr.",
        "date": "Rechnungsdatum",
        "due": "Fällig am",
        "bill_to": "Rechnungsempfänger",
        "description": "Beschreibung",
        "quantity": "Menge",
        "unit_price": "Einzelpreis",
        "amount": "Betrag",
        "subtotal": "Zwischensumme",
        "total": "Gesamtbetrag",
    },
    payment_terms="Zahlbar innerhalb von {days} Tagen ohne Abzug",
)
FRENCH = Language(
    labels={
        "title": "FACTURE",
        "number": "N° de facture",
        "date": "Date de facture",
        "due": "Date d'échéance",
        "bill_to": "Facturé à",
        "description": "Désignation",
        "quantity": "Qté",
        "unit_price": "Prix unitaire",
        "amount": "Montant",
        "subtotal": "Sous-total",
        "total": "Total à payer",
    },
    payment_terms="Paiement à {days} jours",
)
NORWEGIAN = Language(
    labels={
        "title": "FAKTURA",
        "number": "Fakturanr.",
        "date": "Fakturadato",
        "due": "Forfallsdato",
        "bill_to": "Faktureres til",
        "description": "Beskrivelse",
        "quantity": "Antall",
        "unit_price": "Enhetspris",
        "amount": "Beløp",
        "subtotal": "Delsum",
        "total": "Å betale",
    },
    payment_terms="Betaling innen {days} dager",
)

POINT = NumberStyle(decimal_sep=".", group_sep=",")
COMMA = NumberStyle(decimal_sep=",", group_sep=".")
SPACE = NumberStyle(decimal_sep=",", group_sep=" ")

VENDORS: tuple[Vendor, ...] = (
    Vendor(
        key="bluebird",
        name="Bluebird Office Supply Co.",
        address=("1820 Larkspur Avenue", "Dayton, OH 45402", "United States"),
        currency="USD",
        currency_symbol="$",
        symbol_after=False,
        tax_label="Sales tax 7.25%",
        tax_rate=Decimal("0.0725"),
        language=ENGLISH,
        numbers=POINT,
        date_format="%m/%d/%Y",
        number_pattern="INV-{n:05d}",
        page_size="LETTER",
        payment_days=30,
        items=_items(
            "pc",
            ("Copy paper, A-grade, box of 10 reams", "38.00", "55.00"),
            ("Toner cartridge, black, high yield", "64.00", "129.00"),
            ("Ergonomic desk chair", "189.00", "420.00"),
            ("Whiteboard markers, assorted, pack of 12", "9.50", "18.00"),
            ("Monitor arm, dual", "79.00", "149.00"),
            ("Archive boxes, pack of 25", "24.00", "42.00"),
        ),
    ),
    Vendor(
        key="harbor-pine",
        name="Harbor & Pine Logistics LLC",
        address=("77 Wharf Road, Suite 300", "Savannah, GA 31401", "United States"),
        currency="USD",
        currency_symbol="$",
        symbol_after=False,
        tax_label="Tax 0%",
        tax_rate=Decimal("0"),
        language=ENGLISH,
        numbers=POINT,
        date_format="%B %d, %Y",
        number_pattern="HP-{year}-{n:04d}",
        page_size="LETTER",
        payment_days=15,
        items=_items(
            "pc",
            ("Pallet freight, Savannah to Atlanta", "210.00", "480.00"),
            ("Container drayage, 40ft", "650.00", "1150.00"),
            ("Liftgate delivery surcharge", "45.00", "95.00"),
            ("Warehouse storage, per pallet-week", "12.00", "22.00"),
            ("Fuel surcharge", "35.00", "160.00"),
        ),
    ),
    Vendor(
        key="kestrel",
        name="Kestrel Analytik GmbH",
        address=("Lindenstraße 14", "10969 Berlin", "Deutschland"),
        currency="EUR",
        currency_symbol="€",
        symbol_after=True,
        tax_label="USt. 19 %",
        tax_rate=Decimal("0.19"),
        language=GERMAN,
        numbers=COMMA,
        date_format="%d.%m.%Y",
        number_pattern="RE-{year}{n:04d}",
        page_size="A4",
        payment_days=14,
        items=_items(
            "h",
            ("Datenanalyse und Auswertung", "95.00", "140.00"),
            ("Workshop Dashboard-Konzeption", "110.00", "160.00"),
            ("Projektmanagement", "85.00", "120.00"),
            ("Datenbereinigung", "70.00", "105.00"),
            ("Schulung Berichtswesen", "90.00", "130.00"),
        ),
    ),
    Vendor(
        key="lumiere",
        name="Atelier Lumière SARL",
        address=("8 rue des Tanneurs", "69002 Lyon", "France"),
        currency="EUR",
        currency_symbol="€",
        symbol_after=True,
        tax_label="TVA 20 %",
        tax_rate=Decimal("0.20"),
        language=FRENCH,
        numbers=SPACE,
        date_format="%d/%m/%Y",
        number_pattern="F{year}/{n:03d}",
        page_size="A4",
        payment_days=30,
        items=_items(
            "h",
            ("Conception graphique", "60.00", "95.00"),
            ("Retouche photo", "45.00", "70.00"),
            ("Mise en page brochure", "55.00", "85.00"),
            ("Direction artistique", "80.00", "120.00"),
        ),
    ),
    Vendor(
        key="thames-valley",
        name="Thames Valley Print Ltd",
        address=("Unit 4, Kennet Business Park", "Reading RG1 8QW", "United Kingdom"),
        currency="GBP",
        currency_symbol="£",
        symbol_after=False,
        tax_label="VAT 20%",
        tax_rate=Decimal("0.20"),
        language=ENGLISH,
        numbers=POINT,
        date_format="%d %B %Y",
        number_pattern="TVP{n:06d}",
        page_size="A4",
        payment_days=30,
        items=_items(
            "pc",
            ("Business cards, 400gsm, box of 500", "28.00", "49.00"),
            ("A5 flyers, double-sided, 1000 copies", "85.00", "160.00"),
            ("Roller banner, 850 x 2000 mm", "65.00", "120.00"),
            ("Saddle-stitched brochure, 16 pages", "2.10", "4.80"),
            ("Letterhead, 120gsm, 500 sheets", "55.00", "90.00"),
        ),
    ),
    Vendor(
        key="maple-ridge",
        name="Maple Ridge Software Inc.",
        address=("410 Queen Street West", "Toronto, ON M5V 2A5", "Canada"),
        currency="CAD",
        currency_symbol="CA$",
        symbol_after=False,
        tax_label="HST 13%",
        tax_rate=Decimal("0.13"),
        language=ENGLISH,
        numbers=POINT,
        date_format="%Y-%m-%d",
        number_pattern="MRS-{n:05d}",
        page_size="LETTER",
        payment_days=45,
        items=_items(
            "month",
            ("Team plan subscription, 10 seats", "290.00", "390.00"),
            ("Priority support add-on", "75.00", "140.00"),
            ("Additional storage, 1 TB", "18.00", "35.00"),
            ("Audit log retention add-on", "40.00", "80.00"),
        ),
    ),
    Vendor(
        key="fjordlys",
        name="Fjordlys Systemer AS",
        address=("Strandkaien 22", "5013 Bergen", "Norge"),
        currency="NOK",
        currency_symbol="kr",
        symbol_after=True,
        tax_label="MVA 25 %",
        tax_rate=Decimal("0.25"),
        language=NORWEGIAN,
        numbers=SPACE,
        date_format="%d.%m.%Y",
        number_pattern="{year}-{n:05d}",
        page_size="A4",
        payment_days=14,
        items=_items(
            "pc",
            ("Bærbar PC, 14 tommer", "11900.00", "18500.00"),
            ("Dokkingstasjon USB-C", "1490.00", "2690.00"),
            ("Oppsett og installasjon", "950.00", "1650.00"),
            ("Trådløst tastatur og mus", "690.00", "1290.00"),
            ("Nettverkssvitsj, 24 porter", "3200.00", "5400.00"),
        ),
    ),
)

CUSTOMERS: tuple[Customer, ...] = (
    Customer("Lindqvist & Ortega Trading", ("Harbour House, 3 Quay Street", "Galway H91 X2Y5")),
    Customer("Northgate Community Clinic", ("250 Elm Street", "Burlington, VT 05401")),
    Customer("Brightwater Studios", ("Rua das Flores 41", "4050-262 Porto")),
)
