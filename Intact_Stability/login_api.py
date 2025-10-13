"""
This module handles user authentication and session management,
including signup, login, and logout functionalities.

"""

from django.contrib import messages
from django.contrib.auth import authenticate, login, get_user_model
from django.http import JsonResponse
from django.shortcuts import render
import uuid
import logging
import random
import json
import base64
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.urls import reverse
from .models import UserAuthKey
from django.http import JsonResponse
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from .models import UserAuthKey
import logging
from .models import UserAuthKey  # adjust this import path if needed
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect, render
import base64
from django.shortcuts import render, redirect
from .models import UserAuthKey
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from .forms import SignUpForm
from .models import (
    UserSession,
)
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie


# @ensure_csrf_cookie
# def get_csrf_token(request):
#     """
#     Generates a CSRF token and sends it to the frontend
#     """
#     csrf_token = get_token(request)
#     return JsonResponse({'csrfToken': csrf_token})

def signup(request):
    """
    Handles user signup.

    If the request method is POST:
        - Validates the signup form.
        - Creates a new user if the form is valid.
        - Logs in the new user.

    If the request method is GET:
        - Renders the signup form.

    Parameters:
    - request: HttpRequest object.

    Returns:
    - HttpResponseRedirect or HttpResponse: Redirects to 'home'
        on successful signup.
    - Rendered signup form on GET request.
    """
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            # Redirect to a success page.
            return redirect("home")
    else:
        form = SignUpForm()
    return render(request, "signup.html", {"form": form})



logger = logging.getLogger(__name__)
@csrf_exempt
def login_view(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST method required"}, status=405)

    data = json.loads(request.body)
    email = data.get("email")
    password = data.get("password")

    User = get_user_model()

    try:
        user_obj = User.objects.get(email=email)
        user = authenticate(request, username=user_obj.username, password=password)
    except User.DoesNotExist:
        user = None

    if not user:
        return JsonResponse(
            {
                "status": "error",
                "error_type": "invalid_credentials",
                "message": "Invalid email or password.",
            },
            status=401,
        )

    user_key, created = UserAuthKey.objects.get_or_create(
        user=user,
        defaults={"auth_key": str(uuid.uuid4())},
    )

    login(request, user)

    return JsonResponse(
        {
            "status": "success",
            "user_id": user.id,
            "auth_key": user_key.auth_key,
            "new_key_created": created,
            "redirect": "/home",
            "user": user.username,
        },
        status=200,
    )


logger = logging.getLogger(__name__)

# @login_required
# def check_auth_key(request):
#     """Check if the authentication key matches the stored key in the database."""
#     user = request.user
#     received_auth_key = request.headers.get("Auth-Key")  # Auth key from the frontend
#     try:
#         user_key = UserAuthKey.objects.get(user=user)
        
#         # If the key does not match, log out the user
#         if received_auth_key != user_key.auth_key:
#             logger.warning(f"Auth key mismatch for user {user.id}. Logging out.")
#             logout(request)
#             return JsonResponse({"valid": False}, status=403)

#         return JsonResponse({"valid": True}, status=200)

#     except UserAuthKey.DoesNotExist:
#         logger.warning(f"Auth key missing for user {user.id}. Logging out.")
#         logout(request)
#         return JsonResponse({"valid": False}, status=403)


def disabled_check_auth_key(request):
    """Explicitly disable the legacy auth-key validation endpoint."""
    return JsonResponse({"valid": False, "detail": "auth key check disabled"}, status=404)



def get_user_email(request):
    if request.method == "POST":
        user_id = request.POST.get("user_id")  # Get user_id from request

        try:
            user = User.objects.get(id=user_id)  # Fetch user by ID
            return JsonResponse({"status": "success", "email": user.email}, status=200)
        except User.DoesNotExist:
            return JsonResponse({"status": "error", "message": "User not found"}, status=404)


@csrf_exempt
def send_otp(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")

            if not email:
                return JsonResponse({"status": "error", "message": "Email is required"}, status=400)

            # Check if email exists in the database
            user = User.objects.filter(email=email).first()
            if not user:
                return JsonResponse({"status": "error", "message": "User with this email does not exist"}, status=404)

            # Generate a **6-digit OTP**
            otp = str(random.randint(100000, 999999))

            user_auth, created = UserAuthKey.objects.get_or_create(user=user)

            # Only update one_timep (OTP), keep auth_key unchanged
            user_auth.one_timep = otp
            user_auth.save()


            # Encode user_id and OTP in Base64
            token_data = f"{user.id}:{otp}"  # Format "user_id:otp"
            encoded_token = base64.urlsafe_b64encode(token_data.encode()).decode()

            # Generate OTP link dynamically
            base_url = request.build_absolute_uri(reverse("verify_otp"))  # Dynamic domain support
            otp_link = f"{base_url}?token={encoded_token}"

            print(f"Generated OTP link for {email}: {otp_link}")  # Debugging - prints OTP link in console

            # Load the HTML email template
            context = {"otp_link": otp_link}
            html_content = render_to_string("email_template.html", context)
            text_content = strip_tags(html_content)  # Fallback text for email clients that do not support HTML

            # Create email message
            subject = "Reset Your Authentication Key"
            sender_email = "noreply@marine-ops.com"  # Change this to your sender email
            recipient_list = [email]

            email_message = EmailMultiAlternatives(subject, text_content, sender_email, recipient_list)
            email_message.attach_alternative(html_content, "text/html")

            # Send email
            try:
                email_message.send()
            except Exception as e:
                return JsonResponse({"status": "error", "message": f"Email sending failed: {str(e)}"}, status=500)

            return JsonResponse({"status": "success", "message": f"OTP link sent to {email}"}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "Invalid JSON format"}, status=400)
        except Exception as e:
            return JsonResponse({"status": "error", "message": f"Internal error: {str(e)}"}, status=500)

    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)

def verify_otp(request):
    try:
        token = request.GET.get("token")  # Get the encoded token

        if not token:
            print("❌ No token found in request")
            return render(request, "error.html", {"message": "The link is expired or invalid. Please request a new one or contact customer support."})

        # Decode the Base64 token
        try:
            decoded_data = base64.urlsafe_b64decode(token).decode()
            user_id, entered_otp = decoded_data.split(":")  # Extract user_id and OTP
            print(f"🔍 Decoded token - User ID: {user_id}, Entered OTP: {entered_otp}")  # Debugging
        except Exception as e:
            print(f"❌ Error decoding token: {e}")
            return render(request, "error.html", {"message": "The link is expired or invalid. Please request a new one or contact customer support."})

        # Fetch the stored OTP from one_timep field
        user_auth = UserAuthKey.objects.filter(user_id=user_id).first()

        if not user_auth:
            print(f"❌ UserAuthKey record not found for user_id {user_id}")
            return render(request, "error.html", {"message": "The link is expired or invalid. Please request a new one or contact customer support."})

        if not user_auth.one_timep:
            print(f"❌ No OTP stored for user_id {user_id} (one_timep is empty)")
            return render(request, "error.html", {"message": "The link is expired or invalid. Please request a new one or contact customer support."})

        print(f"✅ Stored OTP: {user_auth.one_timep}, Entered OTP: {entered_otp}")  # Debugging

        # ✅ Verify OTP and DELETE THE ENTIRE ROW
        if user_auth.one_timep.strip() == entered_otp.strip():
            print("✅ OTP matched! Deleting the UserAuthKey record.")

            user_auth.delete()  # Deletes the entire row from the database

            print(f"✅ UserAuthKey record for user_id {user_id} deleted successfully.")  # Debugging
            
            # Redirect the user to the login page
            return redirect("https://marine-ops.com/")

        else:
            print("❌ Auth key mismatch detected!")  # Debugging
            return render(request, "error.html", {"message": "The link is expired or invalid. Please request a new one or contact customer support."})

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return render(request, "error.html", {"message": "An unexpected error occurred. Please try again or contact support."})


class CustomLogoutView(LogoutView):
    """
    Custom logout view that extends Django's built-in LogoutView.

    This class adds custom logic to delete a specific session associated
    with the user upon logout. After logging out, the user is redirected
    to the login page.

    Attributes:
    - next_page: The URL to redirect to after a successful logout,
      in this case, the login page.
    Methods:
    - dispatch: Overrides the dispatch method to add session deletion
      logic before calling the parent class's dispatch method.
    """

    # next_page = reverse_lazy("login")  # Redirect to login page after logout


    def dispatch(self, request, *args, **kwargs):
        # Custom logic to delete a specific session associated with the user
        if request.user.is_authenticated:
            try:
                user_session = UserSession.objects.get(user=request.user)
                user_session.delete()  # Delete the specific session
            except UserSession.DoesNotExist:
                pass  # If the session doesn't exist, do nothing

            # Call the parent class's dispatch method which handles the logout
        return super(CustomLogoutView, self).dispatch(request, *args, **kwargs)
