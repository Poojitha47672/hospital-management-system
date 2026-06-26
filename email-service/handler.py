import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')

def send_email(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        trigger = body.get('trigger')
        to_email = body.get('to_email')
        name = body.get('name', 'User')

        if trigger == 'SIGNUP_WELCOME':
            subject = 'Welcome to HMS!'
            content = f"""
            <h2>Welcome to HMS, {name}!</h2>
            <p>Your account has been created successfully.</p>
            <p>You can now log in and start using the Hospital Management System.</p>
            """

        elif trigger == 'BOOKING_CONFIRMATION':
            doctor_name = body.get('doctor_name', '')
            date = body.get('date', '')
            start_time = body.get('start_time', '')
            end_time = body.get('end_time', '')
            subject = 'Appointment Booking Confirmed'
            content = f"""
            <h2>Appointment Confirmed!</h2>
            <p>Dear {name},</p>
            <p>Your appointment has been booked successfully.</p>
            <ul>
                <li><strong>Doctor:</strong> Dr. {doctor_name}</li>
                <li><strong>Date:</strong> {date}</li>
                <li><strong>Time:</strong> {start_time} - {end_time}</li>
            </ul>
            <p>Please arrive 10 minutes early.</p>
            """
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Unknown trigger'})
            }

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg.attach(MIMEText(content, 'html'))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())

        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'Email sent successfully for trigger: {trigger}'})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }