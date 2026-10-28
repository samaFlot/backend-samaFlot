import datetime

from django.utils import timezone

from comptes.models import Agent
from flotte.models import Vehicule
from .models import Mission


def recuperer_ressources_admissibles(demande):
    """
    Retourne les véhicules et agents pouvant être proposés
    pour une demande de chargement.
    """

    debut_prevu = timezone.make_aware(
        datetime.datetime.combine(
            demande.date_chargement,
            demande.heure_chargement
        )
    )

    date_fin_prevue = demande.date_fin_prevue

    responsable = demande.responsable

    # ---------------------------------------------------------
    # VÉHICULES
    # ---------------------------------------------------------

    vehicules = Vehicule.objects.filter(
        responsable=responsable,
        etat_technique=Vehicule.EtatTechnique.BON_ETAT,
    ).exclude(
        statut=Vehicule.Statut.EN_PANNE
    ).prefetch_related("documents", "missions")

    vehicules_admissibles = []

    for vehicule in vehicules:

        # Vérifier les documents
        documents = list(vehicule.documents.all())

        if not documents:
            continue

        tous_documents_valides = all(
            document.date_expiration >= timezone.localdate()
            for document in documents
        )

        if not tous_documents_valides:
            continue

        # Vérifier les missions déjà prévues ou en cours
        deja_affecte = any(
            mission.chevauche(debut_prevu, date_fin_prevue)
            for mission in vehicule.missions.all()
            if mission.statut in [
                Mission.Statut.PREVU,
                Mission.Statut.EN_COURS,
            ]
        )

        if deja_affecte:
            continue

        vehicules_admissibles.append(vehicule)

    # ---------------------------------------------------------
    # AGENTS
    # ---------------------------------------------------------

    agents = Agent.objects.filter(
        responsable=responsable,
        disponible=True,
        date_expiration_permis__gte=timezone.localdate(),
    ).select_related("utilisateur").prefetch_related("missions")

    agents_admissibles = []

    for agent in agents:

        deja_affecte = any(
            mission.chevauche(debut_prevu, date_fin_prevue)
            for mission in agent.missions.all()
            if mission.statut in [
                Mission.Statut.PREVU,
                Mission.Statut.EN_COURS,
            ]
        )

        if deja_affecte:
            continue

        agents_admissibles.append(agent)

    return {
        "vehicules": vehicules_admissibles,
        "agents": agents_admissibles,
    }



def preparer_donnees_pour_ia(demande, ressources):

    donnees = {
        "demande": {
            "id": demande.id,
            "demandeur": demande.demandeur,
            "nombre_vehicules_demandes": demande.nombre_vehicules_demandes,
            "date_chargement": str(demande.date_chargement),
            "heure_chargement": str(demande.heure_chargement),
            "date_fin_prevue": str(demande.date_fin_prevue),
            "point_depart": demande.point_depart,
            "destination": demande.destination,
            "description": demande.description,
        },

        "vehicules": [
            {
                "id": vehicule.id,
                "immatriculation": vehicule.immatriculation,
                "type_vehicule": vehicule.type_vehicule,
                "poids": float(vehicule.poids),
                "hauteur": float(vehicule.hauteur),
                "largeur": float(vehicule.largeur),
            }
            for vehicule in ressources["vehicules"]
        ],

        "agents": [
            {
                "id": agent.id,
                "nom": agent.utilisateur.last_name,
                "prenom": agent.utilisateur.first_name,
                "categorie_permis": agent.categorie_permis,
                "date_expiration_permis": str(
                    agent.date_expiration_permis
                ),
            }
            for agent in ressources["agents"]
        ],
    }

    return donnees




#On sépare bien les responsabilités :

#recuperer_ressources_admissibles()

#« Qui a le droit d'être proposé ? »

#preparer_donnees_pour_ia()

#« Quelles informations dois-je donner à l'IA ? »

#Et plus tard, l'IA aura cette responsabilité :

#« Parmi ces ressources admissibles, quelles combinaisons véhicule + agent sont les plus pertinentes pour cette demande ? »