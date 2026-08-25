# accounts/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.views import LoginView, LogoutView
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from .forms import SignUpForm

class CustomLoginView(LoginView):
    """Custom login view using Django's built-in."""
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True


class CustomLogoutView(LogoutView):
    """Custom logout view using Django's built-in."""
    template_name = 'accounts/logout.html'


@require_http_methods(["GET", "POST"])
def signup_view(request):
    """Handle user registration with invite key."""
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created! You can now log in.')
            return redirect('login')
        else:
            # Form errors will be displayed in template
            pass
    else:
        form = SignUpForm()
    
    return render(request, 'accounts/signup.html', {'form': form})