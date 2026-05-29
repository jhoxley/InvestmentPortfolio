from app.exceptions import InvalidCurrencyError

_ISO_4217_CODES: frozenset[str] = frozenset({
    "AED", "AFN", "ALL", "AMD", "ANG", "AOA", "ARS", "AUD", "AWG", "AZN",
    "BAM", "BBD", "BDT", "BGN", "BHD", "BIF", "BMD", "BND", "BOB", "BRL",
    "BSD", "BTN", "BWP", "BYN", "BZD", "CAD", "CDF", "CHF", "CLP", "CNY",
    "COP", "CRC", "CUP", "CVE", "CZK", "DJF", "DKK", "DOP", "DZD", "EGP",
    "ERN", "ETB", "EUR", "FJD", "FKP", "GBP", "GEL", "GHS", "GIP", "GMD",
    "GNF", "GTQ", "GYD", "HKD", "HNL", "HTG", "HUF", "IDR", "ILS",
    "INR", "IQD", "IRR", "ISK", "JMD", "JOD", "JPY", "KES", "KGS", "KHR",
    "KMF", "KPW", "KRW", "KWD", "KYD", "KZT", "LAK", "LBP", "LKR", "LRD",
    "LSL", "LYD", "MAD", "MDL", "MGA", "MKD", "MMK", "MNT", "MOP", "MRU",
    "MUR", "MVR", "MWK", "MXN", "MYR", "MZN", "NAD", "NGN", "NIO", "NOK",
    "NPR", "NZD", "OMR", "PAB", "PEN", "PGK", "PHP", "PKR", "PLN", "PYG",
    "QAR", "RON", "RSD", "RUB", "RWF", "SAR", "SBD", "SCR", "SDG", "SEK",
    "SGD", "SHP", "SLE", "SLL", "SOS", "SRD", "STN", "SVC", "SYP", "SZL",
    "THB", "TJS", "TMT", "TND", "TOP", "TRY", "TTD", "TVD", "TWD", "TZS",
    "UAH", "UGX", "USD", "UYU", "UZS", "VES", "VND", "VUV", "WST", "XAF",
    "XCD", "XOF", "XPF", "YER", "ZAR", "ZMW", "ZWL",
})


def validate_currency_code(code: str) -> None:
    """Raise InvalidCurrencyError if code is not a recognised ISO 4217 code."""
    if code.upper() not in _ISO_4217_CODES:
        raise InvalidCurrencyError(code)
