import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from .forms import SignupForm
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from .models import AvailabilitySlot
import datetime
from .calendar_utils import get_flow, get_credentials, save_credentials, create_calendar_event
import requests as http_requests

def send_email_notification(trigger, to_email, **kwargs):
    try:
        url = os.getenv('EMAIL_SERVICE_URL', 'http://localhost:3000/dev/send-email')
        payload = {'trigger': trigger, 'to_email': to_email, **kwargs}
        http_requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"Email notification failed: {e}")

def signup_view(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            send_email_notification(
                'SIGNUP_WELCOME',
                user.email,
                name=user.get_full_name()
            )
            if user.is_doctor():
                return redirect('doctor_dashboard')
            else:
                return redirect('patient_dashboard')
    else:
        form = SignupForm()
    return render(request, 'core/signup.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.is_doctor():
                return redirect('doctor_dashboard')
            else:
                return redirect('patient_dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def patient_dashboard(request):
    if not request.user.is_patient():
        return HttpResponseForbidden("Access denied.")
    from .models import User, Appointment
    doctors = User.objects.filter(role='doctor')
    my_appointments = Appointment.objects.filter(patient=request.user).select_related('slot__doctor')
    return render(request, 'core/patient_dashboard.html', {
        'doctors': doctors,
        'my_appointments': my_appointments
    })


@login_required
def doctor_dashboard(request):
    if not request.user.is_doctor():
        return HttpResponseForbidden("Access denied.")
    slots = AvailabilitySlot.objects.filter(doctor=request.user).order_by('date', 'start_time')
    return render(request, 'core/doctor_dashboard.html', {'slots': slots})

@login_required
def add_slot(request):
    if not request.user.is_doctor():
        return HttpResponseForbidden("Access denied.")
    if request.method == 'POST':
        date = request.POST.get('date')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        AvailabilitySlot.objects.create(
            doctor=request.user,
            date=date,
            start_time=start_time,
            end_time=end_time
        )
        return redirect('doctor_dashboard')
    return render(request, 'core/add_slot.html')

from django.db import transaction

@login_required
def book_slot(request, slot_id):
    if not request.user.is_patient():
        return HttpResponseForbidden("Access denied.")

    from .models import Appointment
    import datetime

    try:
        with transaction.atomic():
            slot = AvailabilitySlot.objects.select_for_update().get(id=slot_id, is_booked=False)
            slot.is_booked = True
            slot.save()
            appointment = Appointment.objects.create(patient=request.user, slot=slot)
            
            send_email_notification(
                'BOOKING_CONFIRMATION',
                request.user.email,
                name=request.user.get_full_name(),
                doctor_name=slot.doctor.get_full_name(),
                date=str(slot.date),
                start_time=str(slot.start_time),
                end_time=str(slot.end_time)
)

        # Create calendar events
        slot_date = slot.date
        start_dt = datetime.datetime.combine(slot_date, slot.start_time).strftime('%Y-%m-%dT%H:%M:%S+05:30')
        end_dt = datetime.datetime.combine(slot_date, slot.end_time).strftime('%Y-%m-%dT%H:%M:%S+05:30')
        
        print("DEBUG start_dt:", start_dt)
        print("DEBUG end_dt:", end_dt)
        
        patient_creds = get_credentials(request.user)
        if patient_creds:
            create_calendar_event(
                patient_creds,
                f"Appointment with Dr. {slot.doctor.get_full_name()}",
                start_dt,
                end_dt
            )

        doctor_creds = get_credentials(slot.doctor)
        if doctor_creds:
            create_calendar_event(
                doctor_creds,
                f"Appointment with {request.user.get_full_name()}",
                start_dt,
                end_dt
            )

        return redirect('patient_dashboard')

    except AvailabilitySlot.DoesNotExist:
        return render(request, 'core/booking_failed.html')
    
@login_required
def google_auth(request):
    import secrets
    import hashlib
    import base64

    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b'=').decode()

    flow = get_flow()
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        code_challenge=code_challenge,
        code_challenge_method='S256'
    )
    request.session['oauth_state'] = state
    request.session['code_verifier'] = code_verifier
    request.session['oauth_user_id'] = request.user.id  # ← save user id
    return redirect(auth_url)

def oauth2callback(request):
    from .calendar_utils import exchange_code_for_tokens, save_credentials_from_token
    from .models import User
    
    code = request.GET.get('code')
    code_verifier = request.session.get('code_verifier')
    user_id = request.session.get('oauth_user_id')
    
    token_data, cred_data = exchange_code_for_tokens(code, code_verifier)
    
    try:
        user = User.objects.get(id=user_id)
        save_credentials_from_token(user, token_data, cred_data)
        if user.is_doctor():
            return redirect('doctor_dashboard')
        else:
            return redirect('patient_dashboard')
    except User.DoesNotExist:
        return redirect('login')