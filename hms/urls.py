from django.contrib import admin
from django.urls import path
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('doctor/dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('patient/dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('doctor/add-slot/', views.add_slot, name='add_slot'),
    path('patient/dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('book/<int:slot_id>/', views.book_slot, name='book_slot'),
    path('google-auth/', views.google_auth, name='google_auth'),
    path('oauth2callback/', views.oauth2callback, name='oauth2callback'),
]