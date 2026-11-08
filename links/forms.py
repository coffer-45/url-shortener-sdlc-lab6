from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import URLValidator


class RegistrationForm(UserCreationForm):
    pass


class LinkForm(forms.Form):
    original_url = forms.URLField(label="Початковий URL", max_length=2048)

    def clean_original_url(self):
        url = self.cleaned_data["original_url"]
        URLValidator(schemes=["http", "https"])(url)
        return url
