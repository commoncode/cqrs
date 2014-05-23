from rest_framework.fields import CharField, IntegerField

from ..serializers import CQRSSerializer, CQRSPolymorphicSerializer

from .models import (ModelAAM, ModelAM, ModelAMM, ModelM, ModelMAM, ModelMM,
                     ModelMMM, BoringModel, OneMixingBowl, AnotherMixingBowl)


def make_serializer(model):
    '''
    Create a test serializer for a model.

    Usage::

        ASerializer = make_serializer(ModelA)

    This is equivalent to::

        class ASerializer(CQRSPolymorphicSerializer):
            manual_a3 = CharField(source='calc_a3', max_length=50,
                                  read_only=True)

            class Meta:
                model = ModelA
                fields = 'field_a1',
    '''

    model_ = model

    class Meta:
        model = model_
        fields = ('field_{}1'.format(model.prefix),
                  'manual_{}3'.format(model.prefix))

    # Hey! You see that CQRSPolymorphicSerializer base? **It is a lie.**
    # CQRSSerializerMeta substitutes in its place the model base's serializer,
    # e.g. for ModelMM, (MSerializer,). If it did not do that, then the
    # inherited fields would not come through properly. Yes, this is immensely
    # evil, but can you think of a better way to do it accurately? I repent in
    # sackcloth and ashes, by the way. -- Chris Morgan
    return type(CQRSPolymorphicSerializer)(
        '{}Serializer'.format(model.prefix.upper()),
        (CQRSPolymorphicSerializer,),
        {
            'manual_{}3'.format(model.prefix):
            CharField(source='calc_{}3'.format(model.prefix),
                      max_length=50, read_only=True),
            'Meta': Meta,
            '__module__': __name__,
        })


AAMSerializer = make_serializer(ModelAAM)
AMSerializer = make_serializer(ModelAM)
AMMSerializer = make_serializer(ModelAMM)
MSerializer = make_serializer(ModelM)
MAMSerializer = make_serializer(ModelMAM)
MMSerializer = make_serializer(ModelMM)
MMMSerializer = make_serializer(ModelMMM)


# OK, that's enough polymorphic testing.

class BoringSerializer(CQRSSerializer):
    daft_poem = CharField(source='silly_poetry', max_length=500,
                          read_only=True)

    class Meta:
        model = BoringModel
        fields = 'violets', 'daft_poem'


class OneMixingBowlSerializer(CQRSSerializer):
    total = IntegerField(read_only=True)

    class Meta:
        model = OneMixingBowl
        fields = 'sugar', 'water', 'total'
        # NOT 'flour' (from the mixin) or 'oil'


class AnotherMixingBowlSerializer(CQRSSerializer):

    class Meta:
        model = AnotherMixingBowl
        # fields explicitly omitted. Everything should be included.
