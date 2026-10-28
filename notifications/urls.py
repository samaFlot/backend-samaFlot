from django.urls import path
from .views import NotificationListView, NotificationReadView


urlpatterns = [
    path("", NotificationListView.as_view(), name="notifications"),
    path("<int:pk>/lue/", NotificationReadView.as_view(), name="notification-lue"),
]