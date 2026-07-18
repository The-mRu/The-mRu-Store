from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class CustomRegistrationForm(UserCreationForm):
    # Make email required (Django makes it optional by default)
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email']

    def clean_email(self):
        """Check if the email is already in the database."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 1. Nuke the ugly default username help text
        self.fields['username'].help_text = ''
        
        # 2. Inject Tailwind CSS directly into the input fields
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 mt-1'
            })