"""Synthetic ASCII-only shape hint based on locally audited legacy VIDA IL.

Not a production VIN validator, vehicle resolver, ECU acceptance or diagnostic
implementation. A True result must never be promoted to a positive ECU reply.
"""

LEGACY_PREFIXES = ('YV', 'PN', 'LV', 'LY')


def matches_vida_legacy_ascii_shape(candidate):
    """Approximate the 2014D-derived IsValidVIN predicate for ASCII test data.

    The original .NET method accepts some Unicode decimal digits; this
    deliberately constrained ASCII-only helper makes no equivalence claim
    outside synthetic ASCII inputs, and it does not check ISO VIN validity.
    """
    return (isinstance(candidate, str)
            and candidate.isascii()
            and len(candidate) == 17
            and candidate[:2] in LEGACY_PREFIXES
            and candidate[-6:].isdigit())
