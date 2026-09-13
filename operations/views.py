import datetime
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from comptes.permissions import EstResponsable, EstAgent
from flotte.models import Vehicule
from .models import DemandeChargement, Mission
from .serializers import (
    DemandeChargementListSerializer, DemandeChargementCreateSerializer, DemandeChargementDetailSerializer,
    MissionListSerializer, MissionDetailSerializer, MissionCreateSerializer,
)


class DemandeChargementViewSet(viewsets.ModelViewSet):
    permission_classes = [EstResponsable]
    # Seul un Responsable gère les demandes de chargement — jamais un Agent ni l'Admin

    http_method_names = ["get", "post"]
    # Pas de PUT/PATCH/DELETE : une demande ne se modifie pas après coup,
    # seulement consulter / créer / annuler

    def get_queryset(self):
        # Filtre de sécurité appliqué à TOUTES les actions de ce ViewSet :
        # jamais toutes les demandes de la base, seulement celles du Responsable connecté
        qs = DemandeChargement.objects.filter(
            responsable=self.request.user.responsable
        ).order_by("-date_creation")

        statut = self.request.query_params.get("statut")
        recherche = self.request.query_params.get("recherche")
        # Récupère les paramètres dans l'URL, ex. ?statut=PREVU&recherche=Dakar
        if statut:
            qs = qs.filter(statut=statut)
        if recherche:
            qs = qs.filter(
                Q(demandeur__icontains=recherche) | Q(description__icontains=recherche)
            )
            # Q(...) | Q(...) = condition OU : cherche dans demandeur OU dans description
        return qs

    def get_serializer_class(self):
        # Un serializer différent selon l'action
        if self.action == "create":
            return DemandeChargementCreateSerializer
        elif self.action == "retrieve":
            return DemandeChargementDetailSerializer
        return DemandeChargementListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        demande = serializer.save(responsable=request.user.responsable)
        # Le Responsable vient TOUJOURS de request.user, jamais d'une valeur envoyée
        # par le client — sinon on pourrait créer une demande au nom de quelqu'un d'autre

        return Response(
            DemandeChargementDetailSerializer(demande).data, status=status.HTTP_201_CREATED
        )
        # On répond avec le serializer DETAIL

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        # detail=True : cette action concerne UNE demande précise (id dans l'URL)
        demande = self.get_object()

        if demande.statut != DemandeChargement.Statut.PREVU:
            return Response(
                {"detail": "Seule une demande au statut Prévu peut être annulée."},
                #erreur 400: les données envoyées ne respectent pas les règles attendues
                status=status.HTTP_400_BAD_REQUEST,
            )

        #On cherche les missions liées à cette demande qui sont déjà EN_COURS ou TERMINEE.
        missions_commencees_ou_terminees = demande.missions.filter(
        statut__in=[
            Mission.Statut.EN_COURS,
            Mission.Statut.TERMINEE,
            ]
        )

        if missions_commencees_ou_terminees.exists():
            return Response(
                {
                    "detail": (
                        "Impossible d'annuler cette demande : "
                        "au moins une mission est déjà en cours ou terminée."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # Annulation des missions PREVU
        # ---------------------------------------------------------

        # À ce stade, nous savons qu'il n'existe :
        # - aucune mission EN_COURS
        # - aucune mission TERMINEE
        #
        # Il peut donc rester uniquement des missions PREVU
        # ou ANNULEE.
        #
        # On récupère uniquement les missions PREVU pour les annuler.
        missions_a_annuler = demande.missions.filter(
            statut=Mission.Statut.PREVU
        )

        for mission in missions_a_annuler:

            # La mission passe au statut ANNULEE.
            mission.statut = Mission.Statut.ANNULEE

            # On enregistre la date et l'heure de l'annulation.
            mission.date_annulee = timezone.now()

            # On sauvegarde la modification.
            mission.save()

        # ---------------------------------------------------------
        # Annulation de la demande
        # ---------------------------------------------------------

        # Une fois toutes les missions PREVU annulées,
        # la demande elle-même passe au statut ANNULEE.
        demande.statut = DemandeChargement.Statut.ANNULEE
        demande.save()

        # Retourne la demande mise à jour.
        return Response(
            DemandeChargementDetailSerializer(demande).data,
            status=status.HTTP_200_OK,
        )

class MissionViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post"]
    # Pas de permission_classes fixe : elle varie selon l'action (voir get_permissions)

    def get_permissions(self):
        # Appelée par DRF avant chaque requête — permet des permissions différentes
        # selon self.action, plutôt qu'une seule règle pour tout le ViewSet
        if self.action in ["terminer", "demarrer"]:
            return [EstAgent()]
            # Seul un Agent peut démarrer/terminer une mission (la sienne, vérifié plus bas)
        return [EstResponsable()]
        # Le Responsable gère le reste : lister, créer, consulter

    def get_queryset(self):
        user = self.request.user
        if user.role == "AGENT":
            # Un Agent ne voit QUE les missions où il est l'agent affecté
            return Mission.objects.filter(agent=user.agent).select_related(
                #Dans une requête Django, __ sert à traverser une relation entre les modèles. Ici on traverse la relation agent pour arriver à son utilisateur
                "demande_chargement", "vehicule", "agent__utilisateur"
            )
        # Un Responsable voit toutes les missions liées à SES demandes de chargement
        return Mission.objects.filter(
            demande_chargement__responsable=user.responsable
            # Double underscore : traverse la relation FK pour filtrer sur un champ
            # d'un modèle lié (le "responsable" de la "demande_chargement" de chaque mission)
        ).select_related("demande_chargement", "vehicule", "agent__utilisateur").order_by("-date_creation")
        # select_related(...) précharge ces relations en UNE requête SQL (JOIN).

    def get_serializer_class(self):
        if self.action == "create":
            return MissionCreateSerializer
        elif self.action == "retrieve":
            return MissionDetailSerializer
        return MissionListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"responsable": request.user.responsable}
        )
        # context={...} : seul moyen de transmettre le Responsable connecté au serializer,
        # pour qu'il puisse le lire dans validate() via self.context["responsable"]
        serializer.is_valid(raise_exception=True)
        # is_valid() déclenche validate() dans le serializer, qui fait TOUTES les
        # vérifications métier (appartenance, statut de la demande, chevauchement de
        # période...) — si une seule échoue, la requête s'arrête ici avec un 400 clair
        mission = serializer.save()
        return Response(MissionDetailSerializer(mission).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def demarrer(self, request, pk=None):
        mission = self.get_object()

        if mission.agent.utilisateur_id != request.user.id:
            # Sécurité supplémentaire, même si get_queryset() filtre déjà par agent
            # connecté : ne jamais compter uniquement sur le filtrage de liste pour
            # protéger une action qui modifie des données
            return Response(
                {"detail": "Vous ne pouvez démarrer que vos propres missions."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if mission.statut != Mission.Statut.PREVU:
            # Empêche de démarrer une mission déjà en cours, terminée ou annulée
            return Response(
                {"detail": "Cette mission n'est pas au statut Prévu."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mission.statut = Mission.Statut.EN_COURS
        mission.date_debut = timezone.now()
        mission.save()

        # C'est SEULEMENT ici, au démarrage réel, qu'on réserve les ressources —
        # jamais à la création (mission encore PREVU), pour éviter de bloquer un
        # véhicule/agent pour une mission qui n'a peut-être même pas encore commencé
        mission.vehicule.statut = Vehicule.Statut.EN_MISSION
        mission.vehicule.save()
        mission.agent.disponible = False
        mission.agent.save()

        return Response(MissionDetailSerializer(mission).data)

    @action(detail=True, methods=["post"])
    def terminer(self, request, pk=None):
        mission = self.get_object()

        if mission.agent.utilisateur_id != request.user.id:
            return Response(
                {"detail": "Vous ne pouvez terminer que vos propres missions."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if mission.statut != Mission.Statut.EN_COURS:
            # On ne peut terminer qu'une mission réellement en cours —
            # pas une PREVU (jamais démarrée) ni une déjà TERMINEE/ANNULEE
            return Response(
                {"detail": "Cette mission n'est pas en cours."}, status=status.HTTP_400_BAD_REQUEST
            )

        mission.statut = Mission.Statut.TERMINEE
        mission.date_terminee = timezone.now()
        mission.save()

        # Ici on libère VRAIMENT les ressources, puisqu'elles avaient été réservées
        # au moment du démarrage
        mission.vehicule.statut = Vehicule.Statut.DISPONIBLE
        mission.vehicule.save()
        mission.agent.disponible = True
        mission.agent.save()

        mission.demande_chargement.verifier_completion()
        # Revérifié à CHAQUE fin de mission : c'est peut-être la dernière attendue,
        # auquel cas la demande liée passe automatiquement à "Traité"

        return Response(MissionDetailSerializer(mission).data)

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        # Récupère la mission concernée grâce à son ID dans l'URL.
        mission = self.get_object()

        # Une mission peut être annulée uniquement si elle est :
        # - PREVU : la mission n'a pas encore commencé
        if mission.statut != Mission.Statut.PREVU:
            return Response(
                {
                    "detail": (
                        "Seule une mission prévue "
                        "peut être annulée."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # On recupere la demande de chargement liée.
        demande = mission.demande_chargement

        # On combine la date et l'heure du chargement
        # pour obtenir un seul datetime.
        date_heure_chargement = timezone.make_aware(
            datetime.datetime.combine(
                demande.date_chargement,
                demande.heure_chargement,
            )
        )

        # On vérifie si la date et l'heure du chargement sont déjà passées.
        if date_heure_chargement <= timezone.now():
            return Response(
                {
                    "detail": (
                        "Impossible d'annuler cette mission : "
                        "la date et l'heure du chargement sont déjà passées."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # On passe la mission au statut ANNULEE.
        mission.statut = Mission.Statut.ANNULEE

        # On enregistre la date et l'heure de l'annulation.
        mission.date_annulee = timezone.now()

        # On sauvegarde la mission.
        mission.save()

        # On vérifie si la demande de chargement liée
        # doit être mise à jour.
        mission.demande_chargement.verifier_completion()

        # On retourne la mission après son annulation.
        return Response(
            MissionDetailSerializer(mission).data,
            status=status.HTTP_200_OK,
        )
