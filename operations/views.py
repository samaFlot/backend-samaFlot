import datetime
import os
import hmac
from comptes.models import Responsable
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Q
from comptes.permissions import EstResponsable, EstAgent
from flotte.models import Vehicule
from .models import DemandeChargement, Mission
from flotte.serializers import AgentListSerializer
from flotte.serializers import VehiculeSerializer
from notifications.models import Notification
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

    @action(detail=True, methods=["get"], url_path="ressources-disponibles")
    def ressources_disponibles(self, request, pk=None):
        """
        1. L'utilisateur ouvre "Créer une mission" depuis le détail d'une demande
        2. Les sélecteurs Véhicule et Agent sont VIDES et DÉSACTIVÉS au départ
        3. L'utilisateur saisit "Date et heure de fin prévue"
        4. Dès que ce champ est rempli (ou à chaque modification), le frontend appelle :
        GET /demandes-chargement/{id}/ressources-disponibles/?date_fin_prevue=...
        5. La réponse remplit dynamiquement les deux sélecteurs — l'utilisateur ne voit
        QUE des véhicules/agents réellement libres sur cette période précise
        6. À la soumission, POST /missions/ avec ces IDs — comme la même logique de
        chevauchement a déjà filtré la liste, le risque de rejet à la création devient
        quasi nul (sauf cas de double-clic simultané très rare, mais la validation
        backend reste le vrai garde-fou final, jamais uniquement le frontend)
        """
        demande = self.get_object()
        # get_object() applique automatiquement get_queryset() + les permissions :
        # si cette demande n'appartient pas au Responsable connecté, 404 direct

        # --- Récupération et validation du paramètre reçu ---
        date_fin_str = request.query_params.get("date_fin_prevue")
        # query_params : car c'est un paramètre dans l'URL (?date_fin_prevue=...)

        if not date_fin_str:
            return Response(
                {"detail": "Le paramètre date_fin_prevue est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        date_fin_prevue = parse_datetime(date_fin_str)
        # parse_datetime() : convertit la chaîne reçue (ex. "2026-09-20T14:00:00Z")
        # en véritable objet datetime Python — renvoie None si le format est invalide,
        # d'où la vérification juste après
        if date_fin_prevue is None:
            return Response(
                {"detail": "Format de date invalide (attendu : ISO 8601)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Calcul du début de la période, à partir de la demande ---
        debut_prevu = timezone.make_aware(
            datetime.datetime.combine(demande.date_chargement, demande.heure_chargement)
        )

        if date_fin_prevue <= debut_prevu:
            # Vérification de cohérence avant même de chercher les ressources :
            # inutile de calculer quoi que ce soit si la date est absurde
            return Response(
                {"detail": "La date de fin doit être après la date de chargement."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        responsable = demande.responsable
        # On récupère le Responsable via la demande elle-même 

        # --- Véhicules libres sur cette période ---

        vehicules_candidats = Vehicule.objects.filter(
            responsable=responsable
        ).exclude(statut=Vehicule.Statut.EN_PANNE)
        # Premier filtre simple : tous les véhicules de l'entreprise, SAUF ceux en
        # panne — un véhicule en panne n'est jamais proposable, quelle que soit la
        # période demandée

        vehicules_libres = [
            v for v in vehicules_candidats
            if not any(
                m.chevauche(debut_prevu, date_fin_prevue)
                for m in v.missions.filter(statut__in=[Mission.Statut.PREVU, Mission.Statut.EN_COURS])
            )
        ]
        # - Pour CHAQUE véhicule candidat (v)...
        # - ...on regarde TOUTES ses missions actives (celles PREVU ou EN_COURS)
        # - ...et on vérifie si AU MOINS UNE d'entre elles chevauche la période
        #   demandée (any(...) s'arrête dès qu'il en trouve une, pas besoin de
        #   toutes les vérifier)
        # - not any(...) = "aucune de ses missions ne chevauche" = ce véhicule
        #   est libre sur cette période → on le garde dans la liste
        #
        # C'est exactement le même appel à mission.chevauche(...) que dans
        # MissionCreateSerializer.validate() — un seul endroit où cette logique
        # est définie (sur le modèle Mission)

        # --- Agents libres sur cette période : même principe, appliqué aux agents ---
        from comptes.models import Agent
        # Import placé ici (dans la méthode) plutôt qu'en haut du fichier, pour
        # éviter un import circulaire entre operations/ et comptes/ si jamais
        # comptes/models.py importait un jour quelque chose depuis operations/ —

        agents_candidats = Agent.objects.filter(responsable=responsable).select_related("utilisateur")
        # select_related("utilisateur") : précharge le CustomUser lié en une seule

        agents_libres = [
            a for a in agents_candidats
            if not any(
                m.chevauche(debut_prevu, date_fin_prevue)
                for m in a.missions.filter(statut__in=[Mission.Statut.PREVU, Mission.Statut.EN_COURS])
            )
        ]

        return Response({
            "vehicules": VehiculeSerializer(vehicules_libres, many=True).data,
            "agents": AgentListSerializer(agents_libres, many=True).data,
        })
        # On renvoie les DEUX listes dans une seule réponse — le frontend n'a besoin
        # que d'UN SEUL appel à cet endpoint pour peupler les deux sélecteurs
        # (véhicule ET agent) d'un coup, plutôt que deux requêtes séparées

class MissionViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post"]
    # Pas de permission_classes fixe : elle varie selon l'action (voir get_permissions)

    def get_permissions(self):
        # L'Agent et le Responsable peuvent
        # consulter la liste et le détail des missions.
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        
        # Appelée par DRF avant chaque requête — permet des permissions différentes
        # selon self.action, plutôt qu'une seule règle pour tout le ViewSet
        if self.action in ["demarrer", "terminer"]:
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

        # Vérifie que la mission appartient bien à l'Agent connecté
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

        # Vérifie que l'Agent n'a pas déjà une mission en cours.
        # Un Agent ne peut avoir qu'une seule mission EN_COURS à la fois.
        mission_en_cours = Mission.objects.filter(
            agent=mission.agent,
            statut=Mission.Statut.EN_COURS,
        ).exists()

        # Si une mission est déjà en cours, on bloque le démarrage.
        if mission_en_cours:
            return Response(
                {
                    "detail": (
                        "Vous avez déjà une mission en cours. "
                        "Terminez-la avant de démarrer une nouvelle mission."
                    )
                },
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

        Notification.objects.create(
            responsable=mission.demande_chargement.responsable,
            type=Notification.Type.MISSION_DEMARREE,
            titre="Mission démarrée",
            message=(
                 f"L'agent {mission.agent.utilisateur.prenom} "
                f"{mission.agent.utilisateur.nom} a démarré "
                f"la mission #{mission.id}."
            ),
            mission=mission,
        )

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


        Notification.objects.create(
            responsable=mission.demande_chargement.responsable,
            type=Notification.Type.MISSION_TERMINEE,
            titre="Mission terminée",
            message=(
                f"L'agent {mission.agent.utilisateur.prenom} "
                f"{mission.agent.utilisateur.nom} a terminé "
                f"la mission #{mission.id}."
            ),
            mission=mission,
        )

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


@api_view(["POST"])
@permission_classes([AllowAny])
def creer_demande_depuis_n8n(request):
    # Secret configuré dans Django
    secret_attendu = os.getenv("N8N_WEBHOOK_SECRET")

    # Secret envoyé par n8n
    secret_recu = request.headers.get("X-N8N-Secret")

    # Vérification de sécurité
    if not secret_attendu or not secret_recu:
        return Response(
            {"detail": "Non autorisé."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not hmac.compare_digest(secret_recu, secret_attendu):
        return Response(
            {"detail": "Non autorisé."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Récupérer l'identifiant du Responsable
    responsable_id = request.data.get("responsable")

    if not responsable_id:
        return Response(
            {"detail": "Le champ responsable est obligatoire."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Vérifier que le Responsable existe
    responsable = Responsable.objects.filter(id=responsable_id).first()

    if not responsable:
        return Response(
            {"detail": "Responsable introuvable."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Valider les données de la demande
    serializer = DemandeChargementCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Créer la demande avec le Responsable trouvé
    demande = serializer.save(responsable=responsable)

    return Response(
        DemandeChargementDetailSerializer(demande).data,
        status=status.HTTP_201_CREATED,
    )