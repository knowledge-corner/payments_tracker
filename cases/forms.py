import re
from decimal import Decimal

from django import forms
from django.utils import timezone

from accounts.models import Doctor
from contacts.models import Contact, Surgeon
from contacts.services import ensure_affiliation
from core.forms import StyledModelForm
from hospitals.models import Hospital
from payments.models import Payment

from .models import Case

COMMON_PROCEDURES = [
    "General anaesthesia (GA)",
    "Spinal anaesthesia",
    "Epidural",
    "Combined spinal-epidural (CSE)",
    "LSCS - spinal",
    "Peripheral nerve block",
    "Monitored anaesthesia care / sedation",
    "Labour analgesia",
    "Endoscopy sedation",
    "ICU / emergency call",
]


class CaseForm(StyledModelForm):
    paid_now = forms.BooleanField(
        required=False, label="Payment already received",
        help_text="Tick if the hospital/patient paid on the spot.",
    )
    paid_amount = forms.DecimalField(required=False, min_value=Decimal("0.01"), max_digits=10, decimal_places=2)
    paid_mode = forms.ChoiceField(choices=Payment.MODE_CHOICES, required=False, initial="upi", label="Mode")
    # Quick "new contact" on the case form
    new_contact_name = forms.CharField(required=False, max_length=100, label="Contact name")
    new_contact_phone = forms.CharField(required=False, max_length=20, label="Mobile",
                                        widget=forms.TextInput(attrs={"type": "tel", "inputmode": "tel"}))
    new_contact_role = forms.ChoiceField(required=False, choices=Contact.ROLE_CHOICES, initial="billing", label="Role")
    # Quick "new surgeon" on the case form
    new_surgeon_name = forms.CharField(required=False, max_length=100, label="Surgeon name",
                                       widget=forms.TextInput(attrs={"placeholder": "e.g. Dr. Kulkarni"}))
    new_surgeon_phone = forms.CharField(required=False, max_length=20, label="Mobile (optional)",
                                        widget=forms.TextInput(attrs={"type": "tel", "inputmode": "tel"}))

    class Meta:
        model = Case
        fields = ["doctor", "hospital", "case_date", "patient_name", "surgeon", "contact", "patient_reference",
                  "procedure_type", "fee", "due_date", "notes"]
        widgets = {
            "case_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fee": forms.NumberInput(attrs={"inputmode": "decimal", "step": "1", "placeholder": "e.g. 6000"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "procedure_type": forms.TextInput(attrs={"list": "procedure-options", "autocomplete": "off"}),
            "patient_reference": forms.TextInput(attrs={"autocomplete": "off", "placeholder": "e.g. IP 45821 / bill no."}),
            "patient_name": forms.TextInput(attrs={"autocomplete": "off", "placeholder": "e.g. Sunita Patil"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["fee"].required = True
        self.fields["fee"].label = "Fee (₹)"

        # Hospital: type-to-search against the whole directory (server-side).
        hospital_field = self.fields["hospital"]
        hospital_field.queryset = Hospital.objects.all()
        selected = self.data.get(self.add_prefix("hospital")) or self.initial.get("hospital") or (
            self.instance.hospital_id if self.instance.pk else None)
        choices = [("", "Search hospital")]
        if selected and str(selected).isdigit():
            h = Hospital.objects.filter(pk=selected).first()
            if h:
                choices.append((h.pk, h.label))
        hospital_field.widget.choices = choices
        hospital_field.widget.attrs.update({
            "data-searchable": "", "data-search-url": "/hospitals/search/",
            "data-placeholder": "Type hospital name or area", "data-add-url": "/hospitals/add/?next=/cases/add/",
        })

        # Contact and surgeon: the doctor's own lists (re-ordered in the browser once a hospital is picked).
        doctor = self._doctor()
        surgeons = Surgeon.objects.filter(is_active=True)
        surgeons = surgeons.filter(doctor=doctor) if doctor else (surgeons if user and user.is_app_admin else surgeons.none())
        self.fields["surgeon"].queryset = surgeons
        self.fields["surgeon"].empty_label = "Not specified"
        self.fields["surgeon"].label = "Surgeon"
        contacts = Contact.objects.filter(is_active=True)
        contacts = contacts.filter(doctor=doctor) if doctor else (contacts if user and user.is_app_admin else contacts.none())
        self.fields["contact"].queryset = contacts
        self.fields["contact"].empty_label = "Not specified"
        self.fields["contact"].label = "Contact person"

        if user is not None and user.is_app_admin:
            self.fields["doctor"].queryset = Doctor.objects.filter(is_active=True)
        else:
            self.fields.pop("doctor")

        if self.instance.pk:
            for name in ("paid_now", "paid_amount", "paid_mode"):
                self.fields.pop(name)

    def _doctor(self):
        if self.user is None:
            return None
        if self.user.is_app_admin:
            doctor_id = self.data.get(self.add_prefix("doctor")) or self.initial.get("doctor") or (
                self.instance.doctor_id if self.instance.pk else None)
            return Doctor.objects.filter(pk=doctor_id).first() if doctor_id else self.user.doctor_profile
        return self.user.doctor_profile

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("paid_now"):
            amount = cleaned.get("paid_amount") or cleaned.get("fee")
            fee = cleaned.get("fee")
            if not amount:
                self.add_error("paid_amount", "Enter the amount received.")
            elif fee is not None and amount > fee:
                self.add_error("paid_amount", "Amount received cannot be more than the fee.")
            cleaned["paid_amount"] = amount
        case_date = cleaned.get("case_date")
        if case_date and case_date > timezone.localdate():
            self.add_error("case_date", "Case date cannot be in the future.")
        due = cleaned.get("due_date")
        if due and case_date and due < case_date:
            self.add_error("due_date", "Expected payment date cannot be before the case date.")
        doctor = cleaned.get("doctor") or self._doctor()
        contact = cleaned.get("contact")
        if contact and doctor and contact.doctor_id != doctor.pk:
            self.add_error("contact", "This contact belongs to another doctor.")
        surgeon = cleaned.get("surgeon")
        if surgeon and doctor and surgeon.doctor_id != doctor.pk:
            self.add_error("surgeon", "This surgeon belongs to another doctor.")
        if cleaned.get("new_contact_name") and not cleaned.get("new_contact_phone"):
            self.add_error("new_contact_phone", "Add a mobile number for the new contact.")
        return cleaned

    def save_contact(self, case):
        """Create the quick new contact / surgeon and link them to this case's hospital."""
        data = self.cleaned_data
        surgeon = case.surgeon if case.surgeon_id else None
        if data.get("new_surgeon_name"):
            name = re.sub(r"\s+", " ", data["new_surgeon_name"]).strip()
            # Same name already saved by this doctor -> reuse instead of a duplicate.
            surgeon = Surgeon.objects.filter(doctor=case.doctor, name__iexact=name).first()
            if surgeon is None:
                surgeon = Surgeon.objects.create(doctor=case.doctor, name=name,
                                                 phone=(data.get("new_surgeon_phone") or "").strip())
            case.surgeon = surgeon
            case.save(update_fields=["surgeon", "updated_at"])
        if surgeon:
            surgeon.link_hospital(case.hospital)
        contact = None
        if data.get("new_contact_name"):
            phone = data["new_contact_phone"].strip()
            # Same mobile already saved by this doctor -> reuse that contact instead of a duplicate.
            digits = re.sub(r"\D", "", phone)[-10:]
            contact = next((c for c in Contact.objects.filter(doctor=case.doctor)
                            if digits and re.sub(r"\D", "", c.phone)[-10:] == digits), None)
            if contact is None:
                contact = Contact.objects.create(
                    doctor=case.doctor, name=data["new_contact_name"].strip(),
                    phone=phone, role=data.get("new_contact_role") or "billing",
                )
            case.contact = contact
            case.save(update_fields=["contact", "updated_at"])
        elif case.contact_id:
            contact = case.contact
        if contact:
            ensure_affiliation(contact, case.hospital)
        return contact


class CaseImportForm(forms.Form):
    file = forms.FileField(
        label="Excel file (.xlsx)",
        widget=forms.ClearableFileInput(attrs={"accept": ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}),
    )
    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.none(), required=False,
        help_text="Used for rows without a 'Doctor Username'.",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs["class"] = "form-control"
        if user is not None and user.is_app_admin:
            self.fields["doctor"].queryset = Doctor.objects.filter(is_active=True)
            self.fields["doctor"].widget.attrs.update({"class": "form-select", "data-searchable": "", "data-placeholder": "Type to search doctor"})
        else:
            self.fields.pop("doctor")

    def clean_file(self):
        from .importer import MAX_FILE_BYTES

        f = self.cleaned_data["file"]
        if not f.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Please upload an Excel .xlsx file. (In Excel: File > Save As > Excel Workbook.)")
        if f.size > MAX_FILE_BYTES:
            raise forms.ValidationError("File is larger than 5 MB. Please split it into smaller files.")
        return f
