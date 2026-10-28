from django.conf import settings
from django.core.mail import EmailMessage
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from .serializers import ContactSerializer


class ContactView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ContactSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        email = EmailMessage(
            subject="Nouveau message de contact - SamaFlot",
            body=f"""
            Nouveau message reçu depuis le formulaire de contact SamaFlot.

            Nom complet : {data['fullName']}
            Entreprise : {data['company']}
            Téléphone : {data['phone']}
            Email : {data['email']}

            Message :
            {data['message']}
            """,        
            #expéditeur du mail
            from_email=settings.DEFAULT_FROM_EMAIL,
            #adresse doit-on envoyer le mail
            to=[settings.EMAIL_HOST_USER],
            #Quand l'admin clique sur "Répondre", à quelle adresse la réponse doit-elle être envoyée ?
            reply_to=[data["email"]],
        )
        #envoie cet email via le serveur SMTP configuré
        #avec fail_silently=False, on dit à Django s'il y a une erreur pendant l'envoi, ne la cache pas. Signale-moi l'erreur
        email.send(fail_silently=False)

        return Response(
            {
                "message": "Votre message a été envoyé avec succès."
            },
            status=status.HTTP_200_OK
        )