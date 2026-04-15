from __future__ import annotations

from typing import Dict


class PassthroughAdapter:
    """
    Placeholder adapter used for framework tests: returns the record as-is.
    """

    def convert(self, record: Dict) -> Dict:
        return record

