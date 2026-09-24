from rest_framework import serializers


class SerializerCreateUpdateMixin:
    """
    Provide default create/update to satisfy abstract BaseSerializer
    contract for linters.
    """

    def create(self, validated_data):  # type: ignore[override]
        return validated_data

    def update(self, _instance, validated_data):  # type: ignore[override]
        return validated_data


class DatePartSerializer(SerializerCreateUpdateMixin, serializers.Serializer):
    year = serializers.IntegerField(min_value=1)
    month = serializers.IntegerField(min_value=1, max_value=12)
    day = serializers.IntegerField(min_value=1, max_value=31)


class TimePartSerializer(SerializerCreateUpdateMixin, serializers.Serializer):
    hour = serializers.IntegerField(min_value=0, max_value=23)
    min = serializers.IntegerField(min_value=0, max_value=59)
    sec = serializers.IntegerField(min_value=0, max_value=59)


class PlaceSerializer(SerializerCreateUpdateMixin, serializers.Serializer):
    name = serializers.CharField()
    lat = serializers.FloatField()
    lon = serializers.FloatField()
    timezone = serializers.FloatField()


class BirthDataSerializer(SerializerCreateUpdateMixin, serializers.Serializer):
    DOB = DatePartSerializer()
    TOB = TimePartSerializer()
    POB = PlaceSerializer()
    name = serializers.CharField(required=False, allow_blank=True)


class WorkflowInSer(SerializerCreateUpdateMixin, serializers.Serializer):
    question = serializers.CharField()
    birthdata = BirthDataSerializer()
