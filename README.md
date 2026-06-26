## Setup and Run

### Prerequisites
- Python 3.11
- PostgreSQL 18
- Node.js v24+
- Gmail account with App Password

### 1. Clone and Install

```bash
git clone <your-repo-url>
cd hospital-management-system
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the root:

```bash
SECRET_KEY=your-django-secret-key
DEBUG=True
DB_NAME=hms_db
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432
EMAIL_SERVICE_URL=http://localhost:3000/dev/send-email
```

### 3. Database Setup

```bash
psql -U postgres
CREATE DATABASE hms_db;
\q

python manage.py migrate
```

### 4. Google Calendar Setup

- Create a Google Cloud project
- Enable Google Calendar API
- Create OAuth2 credentials (Web application)
- Add `http://localhost:8000/oauth2callback/` as redirect URI
- Download credentials and save as `credentials.json` in root

### 5. Run the Django App

```bash
python manage.py runserver
```

### 6. Run the Serverless Email Service

In a separate terminal:

```bash
cd email-service
npm install
serverless offline
```

The email service runs on `http://localhost:3000/dev/send-email`

### 7. Access the App

- Open `http://127.0.0.1:8000`
- Sign up as Doctor → set availability slots
- Sign up as Patient → view slots → book appointment
- Connect Google Calendar from dashboard for calendar events

---

## System Architecture

### Overview

The system has two independently running services:

1. **Django App** (port 8000) - handles auth, slot management, booking, and Google Calendar integration
2. **Serverless Email Service** (port 3000) - a separate Python Lambda function running locally via serverless-offline

### How They Connect

When a booking or signup happens in Django, it makes an HTTP POST request to the serverless email service at `http://localhost:3000/dev/send-email` with a JSON payload containing the trigger type and user details. The serverless function handles the email sending via Gmail SMTP independently.

### Data Model

- `User` - extends Django's AbstractUser with a `role` field (doctor/patient)
- `AvailabilitySlot` - belongs to a doctor, has date/time range and `is_booked` flag
- `Appointment` - links a patient to a slot via OneToOneField
- `GoogleToken` - stores OAuth2 tokens per user for Calendar API access

### Role-Based Access

Every protected view checks `request.user.is_doctor()` or `request.user.is_patient()` and returns `HttpResponseForbidden` if the role doesn't match. Doctors cannot access patient actions and vice versa.

### Google Calendar Integration

OAuth2 flow with PKCE is used. When a user connects their Google Calendar, tokens are stored in the `GoogleToken` model. On booking confirmation, the system creates calendar events for both the doctor and patient using the Google Calendar API with their respective stored credentials.

---

## The Design Decision

### Problem: Handling Concurrent Slot Booking (Race Condition)

When two patients attempt to book the same available slot simultaneously, both could read `is_booked=False`, both could pass the availability check, and both could create an appointment, resulting in double booking.

### Two Approaches Considered

**Option A: Application-level check**
Check `is_booked` in Python before saving. Simple to implement but not safe, two requests running simultaneously can both pass the check before either saves.

**Option B: Database-level locking with `select_for_update()`**
Wrap the booking in a `transaction.atomic()` block and use `select_for_update()` to lock the slot row at the database level while it's being processed.

### Decision: Option B - `select_for_update()`

I chose database-level locking because it makes the race condition physically impossible, not just unlikely. PostgreSQL guarantees that only one transaction can hold the lock on a row at a time. The second request will wait until the first transaction completes - if the slot is already booked, it gets a `DoesNotExist` exception and is shown a "Booking Failed" page. This is the correct solution because correctness here is non-negotiable: a double booking in a medical system has real consequences. Application-level checks give a false sense of safety under concurrent load.

---

## Limitations

### What Would Break in Production

1. **OAuth token expiry** - Access tokens expire after 1 hour. The current implementation does not handle token refresh automatically. In production, `google.auth.transport.requests.Request()` should be used to refresh expired tokens before API calls.

2. **Serverless cold starts** - The email function running via serverless-offline has no warm-up. In production on AWS Lambda, cold starts could delay email delivery by 2-3 seconds.

3. **Single Google account assumption** - The task assumes one Google account per user. In production, users may have multiple accounts or revoke access, which would break calendar event creation silently.

4. **No email queue** - Emails are sent synchronously via a direct HTTP call. If the serverless service is down, the email fails silently. A proper queue (SQS, Celery) should be used in production.

5. **Credentials in filesystem** - `credentials.json` is stored on disk. In production, this should be stored in environment variables or a secrets manager.

### What I Would Fix First

Token refresh handling, because expired tokens would silently break Google Calendar integration for any user who connected their calendar more than an hour ago, making a core feature unreliable.