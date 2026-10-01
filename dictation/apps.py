from django.apps import AppConfig


class DictationConfig(AppConfig):
    """Optional "Dictate a case" add-on (speech to text on the Add Case form).

    Self-contained (parser, page, script all live in this folder) and no
    database tables. To switch it off set FEATURE_DICTATION=0 in .env; to remove
    it for good just delete this folder - settings and URLs notice automatically.
    """

    name = "dictation"
    verbose_name = "Dictation (add-on)"
