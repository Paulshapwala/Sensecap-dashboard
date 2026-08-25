# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.models import User

# No custom models needed for invite-only auth, so nothing to register
# Django's User model is already in admin by default

admin.site.site_header = "Weather Dashboard Admin"
admin.site.site_title = "Weather Dashboard"
admin.site.index_title = "Welcome to the Admin Panel"