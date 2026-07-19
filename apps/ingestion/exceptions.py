class ParseError(Exception):
    """Raised by ingestion.process_payload when a TTN payload is malformed,
    is missing a required sensor measurement, or contains a value outside
    its physically plausible range.

    Per the interface contract, this is the *only* exception this app
    raises across its public boundary.
    """
    pass