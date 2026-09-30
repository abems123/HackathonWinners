from django import forms
from .domain.passage import normalize_newlines
from .models import Pin, User


class ActionForm(forms.Form):
    action = forms.ChoiceField(
        choices=[
            (v, v.replace("_", " ").capitalize())
            for v in [
                "confirm",
                "supersede",
                "does_not_apply",
                "add_exception",
                "escalate",
                "dismiss",
                "ask",
                "source_outdated",
                "answer",
            ]
        ]
    )
    reason = forms.CharField(
        max_length=3000,
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "Explain your decision for the next person…"}
        ),
    )
    quote = forms.CharField(
        required=False, max_length=50000, widget=forms.Textarea(attrs={"rows": 4})
    )
    version_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    related_pin = forms.ModelChoiceField(queryset=Pin.objects.none(), required=False)
    expert = forms.ModelChoiceField(queryset=User.objects.none(), required=False)
    valid_until = forms.DateTimeField(
        required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )


class UploadForm(forms.Form):
    content = forms.CharField(
        required=False,
        max_length=200000,
        widget=forms.Textarea(attrs={"rows": 12, "placeholder": "Paste the new source text…"}),
    )
    file = forms.FileField(required=False, help_text="UTF-8 Markdown or text, maximum 1 MB.")
    effective_from = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    effective_to = forms.DateTimeField(
        required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )

    def clean(self):
        values = super().clean()
        values["content"] = normalize_newlines(values.get("content") or "")
        upload = values.get("file")
        if upload:
            if upload.size > 1024 * 1024 or not upload.name.lower().endswith((".md", ".txt")):
                raise forms.ValidationError("Upload a Markdown or text file smaller than 1 MB.")
            try:
                values["content"] = normalize_newlines(upload.read().decode("utf-8-sig"))
            except UnicodeDecodeError as exc:
                raise forms.ValidationError("The file must use UTF-8 encoding.") from exc
            if values["content"].startswith("---"):
                parts = values["content"].split("---", 2)
                if len(parts) == 3:
                    values["content"] = parts[2].strip()
        if not values.get("content", "").strip():
            raise forms.ValidationError("Provide source text or a file.")
        if (
            values.get("effective_to")
            and values.get("effective_from")
            and values["effective_to"] <= values["effective_from"]
        ):
            raise forms.ValidationError("The end date must be after the start date.")
        return values


class ProfileForm(forms.Form):
    country = forms.ChoiceField(
        choices=[("BE", "Belgium"), ("NL", "Netherlands"), ("LU", "Luxembourg")]
    )
    pc = forms.CharField(max_length=20, required=False, label="Joint committee")
    payroll_close = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))
