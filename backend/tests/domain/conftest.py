"""
Test-only compatibility shim: the app targets Python 3.12 (see scripts/portal.ps1),
where `datetime.UTC` is available. Older interpreters used to run the test suite
locally (<3.11) don't have it — backport it so imports don't fail.
This changes nothing about the app's actual runtime behavior.
"""

import datetime as _datetime

if not hasattr(_datetime, "UTC"):
    _datetime.UTC = _datetime.timezone.utc
