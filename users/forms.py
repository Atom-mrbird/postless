from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User

class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email')

class UserUpdateForm(UserChangeForm):
    password = None # Exclude password field from this form
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')
