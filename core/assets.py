"""Cache-busting for our own CSS/JS.

The version is a short hash of the files' contents, so every deploy that
changes them gives new URLs (?v=...) and a new service-worker cache. Phones
then always load the current scripts instead of a stale cached copy.
"""
import hashlib
from functools import lru_cache

from django.contrib.staticfiles import finders

OWN_ASSETS = ["css/app.css", "js/app.js", "js/searchable-select.js", "js/push.js"]


@lru_cache(maxsize=1)
def asset_version():
    digest = hashlib.sha1()
    for path in OWN_ASSETS:
        found = finders.find(path)
        try:
            with open(found, "rb") as fh:
                digest.update(fh.read())
        except (TypeError, OSError):
            continue
    return digest.hexdigest()[:10]
