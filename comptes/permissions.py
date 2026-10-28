# comptes/permissions.py
from rest_framework.permissions import BasePermission
from .models import CustomUser


class EstResponsable(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == CustomUser.Role.RESPONSABLE


class EstAgent(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == CustomUser.Role.AGENT


class EstAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == CustomUser.Role.ADMIN