from django import forms
from .models import Cargo
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class CargoForm(forms.ModelForm):
    class Meta:
        model = Cargo
        fields = '__all__'  # Use '__all__' to include all fields from the model

class SignUpForm(UserCreationForm):
    email = forms.EmailField(max_length=254, help_text='Required. Inform a valid email address.')

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2',)
