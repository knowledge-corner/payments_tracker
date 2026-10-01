"""
Turn a dictated sentence into Add Case fields.

    "Ruby Hall ortho, TKR under spinal, IP 4521, fee 6,500, yesterday,
     payment in 15 days, contact Patil 98220 12345"

The phone's speech recognition produces the text; this module only reads it.
Everything it finds is a suggestion: the form is filled in and the doctor
checks it before saving.
"""
import datetime
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.utils import timezone

from hospitals.models import STOP_WORDS, Department, Hospital, normalise_name

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Spoken shortcuts -> department name (as seeded in hospitals migration 0003).
DEPARTMENT_WORDS = [
    (r"general\s+surg\w*", "General Surgery"),
    (r"ortho\w*|tkr|thr|knee replacement|hip replacement|arthroscop\w*|fracture", "Orthopaedics"),
    (r"gyn\w*|gynaec\w*|obs\w*|obgy\w*|ob\s*gyn\w*|lscs|caesarean|cesarean|c\s*section|labou?r|delivery|hysterectom\w*",
     "Obstetrics & Gynaecology"),
    (r"ent|tonsil\w*|adenoid\w*|septoplasty|fess", "ENT"),
    (r"ophthal\w*|eye|cataract|phaco\w*", "Ophthalmology"),
    (r"uro\w*|turp|pcnl|ursl", "Urology"),
    (r"cardiac|cardio\w*|cabg|cvts|cath\s*lab", "Cardiac / Cardiothoracic"),
    (r"neuro\w*|spine surgery|craniotomy", "Neurosurgery"),
    (r"paed\w*|pediatric\w*", "Paediatric Surgery"),
    (r"plastic\w*|cosmetic", "Plastic Surgery"),
    (r"dental|maxillo\w*|oral surgery", "Dental / Maxillofacial"),
    (r"endoscop\w*|colonoscop\w*|ercp|gastro\w*|\bgi\b", "Endoscopy / GI"),
    (r"onco\w*|cancer", "Oncology"),
    (r"icu|emergency|casualty", "ICU / Emergency"),
]

# Procedure / anaesthesia words worth keeping when no "procedure ..." phrase is said.
PROCEDURE_WORDS = [
    (r"lscs|caesarean|cesarean|c\s*section", "LSCS"),
    (r"tkr|total knee replacement|knee replacement", "TKR"),
    (r"thr|total hip replacement|hip replacement", "THR"),
    (r"lap(?:aroscopic)?\s*chole\w*", "Lap chole"),
    (r"appendic?ectomy", "Appendicectomy"),
    (r"hysterectomy", "Hysterectomy"),
    (r"cataract|phaco\w*", "Cataract"),
    (r"tonsillectomy", "Tonsillectomy"),
    (r"turp", "TURP"),
    (r"hernia\w*", "Hernia repair"),
    (r"cabg", "CABG"),
    (r"endoscopy|colonoscopy|ercp", "Endoscopy"),
    (r"general anaesthesia|general anesthesia|\bga\b", "GA"),
    (r"combined spinal epidural|\bcse\b", "CSE"),
    (r"spinal", "Spinal"),
    (r"epidural", "Epidural"),
    (r"labou?r analgesia", "Labour analgesia"),
    (r"nerve block|\bblock\b", "Nerve block"),
    (r"sedation|\bmac\b", "Sedation"),
]

STOP_PROCEDURE = r"(?:at|in|on|fee|fees|for|rupees|rs|department|dept|contact|ip|uhid|mrd|due|payment|today|yesterday|patient|amount|charges|expected|note|notes)"


@dataclass
class Dictation:
    transcript: str
    case_date: datetime.date | None = None
    fee: Decimal | None = None
    due_date: datetime.date | None = None
    due_days: int | None = None
    hospital: Hospital | None = None
    hospital_alternatives: list = field(default_factory=list)
    department: Department | None = None
    procedure_type: str = ""
    patient_reference: str = ""
    contact: object = None
    new_contact_name: str = ""
    new_contact_phone: str = ""
    notes: str = ""

    def as_json(self, mine=()):
        def hosp(h):
            return {"id": h.pk, "label": h.name, "sub": h.place, "mine": h.pk in mine}

        filled = []
        for label, value in (
            ("Hospital", self.hospital and self.hospital.name), ("Date", self.case_date and f"{self.case_date:%d %b %Y}"),
            ("Fee", self.fee is not None and f"₹{self.fee:,.0f}"), ("Department", self.department and self.department.name),
            ("Procedure", self.procedure_type), ("Patient ref", self.patient_reference),
            ("Contact", self.contact.name if self.contact else (self.new_contact_name and
                                                               f"{self.new_contact_name} (new)")),
            ("Expected payment", self.due_date and f"{self.due_date:%d %b %Y}"), ("Notes", self.notes),
        ):
            if value:
                filled.append({"label": label, "value": value})
        return {
            "transcript": self.transcript,
            "fields": {
                "case_date": self.case_date.isoformat() if self.case_date else None,
                "fee": str(self.fee) if self.fee is not None else None,
                "due_date": self.due_date.isoformat() if self.due_date else None,
                "hospital": hosp(self.hospital) if self.hospital else None,
                "department": self.department.pk if self.department else None,
                "procedure_type": self.procedure_type,
                "patient_reference": self.patient_reference,
                "contact": self.contact.pk if self.contact else None,
                "new_contact_name": self.new_contact_name,
                "new_contact_phone": self.new_contact_phone,
                "notes": self.notes,
            },
            "hospital_alternatives": [hosp(h) for h in self.hospital_alternatives],
            "filled": filled,
            "missing": [name for name, value in (("hospital", self.hospital), ("fee", self.fee)) if not value],
        }


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def _prepare(text):
    t = " " + (text or "").lower().replace("₹", " rupees ").replace("/-", " rupees ") + " "
    t = re.sub(r"(?<=\d),(?=\d)", "", t)                       # 6,500 -> 6500
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(?:k|thousand|hazaar|hazar)\b",
               lambda m: str(int(Decimal(m.group(1)) * 1000)), t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs)\b",
               lambda m: str(int(Decimal(m.group(1)) * 100000)), t)
    return re.sub(r"\s+", " ", t)


def _cut(text, match):
    """Blank out a matched span so later rules don't read it again."""
    return text[:match.start()] + " ; " + text[match.end():]


def _safe_date(year, month, day):
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None


def _date_from(text, today, prefer_past=True):
    """Find one date expression. Returns (date, match) or (None, None)."""
    rules = [
        (r"\bday before yesterday\b", lambda m: today - datetime.timedelta(days=2)),
        (r"\byesterday\b|\blast night\b", lambda m: today - datetime.timedelta(days=1)),
        (r"\btoday\b|\bthis morning\b|\btonight\b", lambda m: today),
        (r"\btomorrow\b", lambda m: today + datetime.timedelta(days=1)),
        (r"\b(\d{1,2})\s*days? ago\b", lambda m: today - datetime.timedelta(days=int(m.group(1)))),
        (rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:of\s+)?({MONTH_RE})\b\.?(?:,?\s*(\d{{4}}))?",
         lambda m: _month_day(int(m.group(3)) if m.group(3) else None, MONTHS[m.group(2)], int(m.group(1)), today, prefer_past)),
        (rf"\b({MONTH_RE})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s*(\d{{4}}))?",
         lambda m: _month_day(int(m.group(3)) if m.group(3) else None, MONTHS[m.group(1)], int(m.group(2)), today, prefer_past)),
        (r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b",
         lambda m: _month_day(_year(m.group(3)), int(m.group(2)), int(m.group(1)), today, prefer_past)),
        (r"\blast (" + "|".join(WEEKDAYS) + r")\b|\bon (" + "|".join(WEEKDAYS) + r")\b",
         lambda m: _last_weekday(m.group(1) or m.group(2), today)),
    ]
    for pattern, build in rules:
        m = re.search(pattern, text)
        if m:
            value = build(m)
            if value:
                return value, m
    return None, None


def _year(text):
    if not text:
        return None
    year = int(text)
    return year + 2000 if year < 100 else year


def _month_day(year, month, day, today, prefer_past):
    if year:
        return _safe_date(year, month, day)
    value = _safe_date(today.year, month, day)
    if value and prefer_past and value > today:
        value = _safe_date(today.year - 1, month, day)
    if value and not prefer_past and value < today - datetime.timedelta(days=60):
        value = _safe_date(today.year + 1, month, day)
    return value


def _last_weekday(name, today):
    delta = (today.weekday() - WEEKDAYS.index(name)) % 7 or 7
    return today - datetime.timedelta(days=delta)


def _phrase(words):
    """Tidy a spoken phrase: keep acronyms upper case, capitalise the first word."""
    out = []
    for w in words.split():
        out.append(w.upper() if w in {"ga", "lscs", "tkr", "thr", "cse", "turp", "cabg", "ercp", "mac", "icu", "ent"} else w)
    text = " ".join(out).strip(" ,.;-")
    return text[:1].upper() + text[1:] if text else ""


# --------------------------------------------------------------------------- #
# Hospital matching
# --------------------------------------------------------------------------- #

GENERIC = STOP_WORDS | {"dr", "sir", "st", "of", "for", "children", "general", "municipal", "memorial", "foundation"}


def _distinct(name):
    return {w for w in normalise_name(name).split() if len(w) > 1 and w not in GENERIC}


def match_hospital(text, mine=()):
    words = set(normalise_name(text).split())
    keys = [w for w in words if len(w) > 2 and w not in GENERIC and not w.isdigit()]
    if not keys:
        return None, []
    query = Q()
    for w in keys:
        query |= Q(name__icontains=w) | Q(aliases__icontains=w)
    scored = []
    for h in Hospital.objects.active().filter(query)[:400]:
        best = 0.0
        for variant in [h.name] + [a for a in h.aliases.split(",") if a.strip()]:
            wanted = _distinct(variant)
            if not wanted:
                continue
            hit = wanted & words
            if not hit or not any(len(w) > 2 for w in hit):
                continue
            best = max(best, len(hit) / len(wanted) + 0.05 * len(hit))
        if best:
            place = _distinct(f"{h.area} {h.city}") & words
            scored.append((best + (0.1 if place else 0) + (0.15 if h.pk in mine else 0), h))
    scored.sort(key=lambda s: (-s[0], s[1].name))
    if not scored or scored[0][0] < 0.5:
        return None, [h for _, h in scored[:3]]
    return scored[0][1], [h for s, h in scored[1:4] if s >= scored[0][0] - 0.2]


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #

def parse(transcript, doctor=None, mine=(), today=None):
    today = today or timezone.localdate()
    result = Dictation(transcript=(transcript or "").strip())
    text = _prepare(result.transcript)

    # Notes: everything after "note(s)" / "remark(s)".
    m = re.search(r"\b(?:notes?|remarks?)\b\s*[:,-]?\s*(.+)$", text)
    if m:
        result.notes = _phrase(m.group(1))
        text = text[:m.start()]

    # Phone number (10 digits starting 6-9), possibly spoken in groups.
    m = re.search(r"(?:\+?\s*91[\s-]*)?\b([6-9]\d{2}[\s-]?\d{2}[\s-]?\d{5}|[6-9]\d{4}[\s-]?\d{5})\b", text)
    phone = ""
    if m:
        phone = re.sub(r"\D", "", m.group(1))
        text = _cut(text, m)

    # Patient / IP reference.
    m = re.search(r"\b(ip|ipd|uhid|mrd|mr|reg(?:istration)?|patient(?:\s+(?:id|ref(?:erence)?|number|no))?)"
                  r"\s*(?:no\.?|number|num|#|id)?\s*[:\-]?\s*([a-z]{0,3}\s?\d[\w/-]*)", text)
    if m:
        prefix = m.group(1).split()[0]
        prefix = "IP" if prefix in ("ip", "ipd", "patient") else prefix.upper()
        result.patient_reference = f"{prefix} {m.group(2).replace(' ', '').upper()}"
        text = _cut(text, m)

    # Expected payment: "payment in 15 days", "due on 5th Nov", "expected by 20/11".
    m = re.search(r"\b(?:due|expected|payment|pay|credit)\b(?:\s+(?:date|period|expected|due|payment|is|will be|by|on|in|within|after|of))*"
                  r"\s*(?P<rest>[^;,.]{0,40})", text)
    if m:
        rest = m.group("rest")
        start = m.start("rest")
        rel = re.match(r"\s*(?:in|within|after)?\s*(\d{1,3})\s*(day|week|month)s?\b", rest)
        if rel:
            n, unit = int(rel.group(1)), rel.group(2)
            result.due_days = n * {"day": 1, "week": 7, "month": 30}[unit]
            text = text[:m.start()] + " ; " + text[start + rel.end():]
        else:
            due, dm = _date_from(rest, today, prefer_past=False)
            if due and not rest[:dm.start()].strip(" ,"):
                result.due_date = due
                text = text[:m.start()] + " ; " + text[start + dm.end():]

    # Case date.
    result.case_date, m = _date_from(text, today, prefer_past=True)
    if m:
        text = _cut(text, m)
    if result.due_days is not None:
        result.due_date = (result.case_date or today) + datetime.timedelta(days=result.due_days)

    # Fee.
    m = (re.search(r"\b(?:fee|fees|charges?|charged|amount|bill(?:ed)?|rupees|rs\.?|inr)\s*(?:of|is|was|:)?\s*(\d+(?:\.\d+)?)\b", text)
         or re.search(r"\b(\d+(?:\.\d+)?)\s*(?:rupees|rs\b|inr\b)", text))
    if not m:
        numbers = [n for n in re.finditer(r"\b(\d{3,7}(?:\.\d+)?)\b", text) if Decimal(n.group(1)) >= 100]
        m = max(numbers, key=lambda n: Decimal(n.group(1)), default=None)
    if m:
        try:
            result.fee = Decimal(m.group(1)).quantize(Decimal("1"))
            text = _cut(text, m)
        except InvalidOperation:
            pass

    # Contact: an existing contact named in the text, or "contact <name>" (+ phone) for a new one.
    if doctor is not None:
        words = set(normalise_name(text).split())
        for contact in doctor.contacts.filter(is_active=True):
            parts = [w for w in normalise_name(contact.name).split() if w not in {"mr", "mrs", "ms", "dr", "sister", "sr"}]
            if parts and all(p in words for p in parts) and re.search(r"\b(contact|spoke|call|with|ask)\b|" +
                                                                      re.escape(parts[0]), text):
                result.contact = contact
                break
    m = re.search(r"\b(?:contact(?:\s+person)?|call|billing person)\s*(?:is|:)?\s*((?:mr|mrs|ms|dr|sister)?\.?\s*[a-z]+(?:\s+[a-z]+)?)", text)
    if m:
        name = m.group(1).strip()
        name_words = name.split()
        if name_words and name_words[-1] in re.findall(r"[a-z]+", STOP_PROCEDURE):
            name = " ".join(name_words[:-1])
        if result.contact is None and name:
            result.new_contact_name = " ".join(w.capitalize() for w in name.replace(".", "").split())
            result.new_contact_phone = phone
        text = _cut(text, m)

    # Department.
    for dept in Department.objects.filter(is_active=True):
        if re.search(r"\b" + re.escape(dept.name.lower()) + r"\b", text):
            result.department = dept
            break
    if result.department is None:
        names = {d.name: d for d in Department.objects.filter(is_active=True)}
        for pattern, name in DEPARTMENT_WORDS:
            if re.search(r"\b(?:" + pattern + r")\b", text) and name in names:
                result.department = names[name]
                break

    # Procedure: explicit phrase first, otherwise recognised keywords.
    m = re.search(r"\b(?:procedure|surgery|operation|case of|case type|anaesthesia type|did)\s*(?:was|is|:)?\s*"
                  r"([a-z][a-z \-]{1,60}?)(?=\s+" + STOP_PROCEDURE + r"\b|\s*[,.;]|\s*$)", text)
    if m and m.group(1).strip() not in ("a", "an", "the"):
        result.procedure_type = _phrase(m.group(1))
    else:
        found = []
        for pattern, label in PROCEDURE_WORDS:
            if re.search(r"\b(?:" + pattern + r")\b", text) and label not in found:
                if label == "Spinal" and "CSE" in found:
                    continue
                found.append(label)
        result.procedure_type = " - ".join(found[:3])

    # Hospital (last, on what is left, so dates/fees/names don't confuse it).
    result.hospital, result.hospital_alternatives = match_hospital(text, mine)
    return result
