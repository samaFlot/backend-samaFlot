from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        responsable = request.user.responsable

        notifications = Notification.objects.filter(
            responsable=responsable
        ).order_by("-date_creation")

        serializer = NotificationSerializer(
            notifications,
            many=True
        )

        return Response(serializer.data)

class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = Notification.objects.get(
            id=pk,
            responsable=request.user.responsable
        )

        notification.lu = True
        notification.save()

        return Response({
            "message": "Notification marquée comme lue."
        })