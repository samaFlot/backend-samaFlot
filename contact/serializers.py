from rest_framework import serializers


class ContactSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=150)
    company = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30)
    email = serializers.EmailField()
    message = serializers.CharField()