from django.db import models
from django.test import TestCase
from django.forms.models import model_to_dict
from rest_framework.fields import CharField
from .models import CQRSPolymorphicModel
from .serializers import CQRSPolymorphicSerializer, CQRSSerializerMeta


class ModelA(CQRSPolymorphicModel):
    field_a1 = models.CharField(max_length=4)
    field_a2 = models.CharField(max_length=5)

    def calc_a3(self):
        return 'from calc_a3'


class ModelB(CQRSPolymorphicModel):
    field_b1 = models.CharField(max_length=6)
    field_b2 = models.CharField(max_length=7)

    def calc_b3(self):
        return 'from calc_b3'


class ModelC(ModelA, ModelB):
    field_c1 = models.CharField(max_length=8)
    field_c2 = models.CharField(max_length=9)


class ModelD(ModelA, ModelB):
    field_d1 = models.CharField(max_length=11)
    field_d2 = models.CharField(max_length=12)


class ASerializer(CQRSPolymorphicSerializer):
    # We can has manually specified fields
    manual_a3 = CharField(source='calc_a3', max_length=12, read_only=True)

    class Meta:
        model = ModelA
        # We can has automatically specified fields, including not including
        # some fields (field_a2 in this case).
        fields = 'field_a1',
        # Although we have not specified 'id' and 'mongoID' here, they will be
        # included due to the inheritance rules.
        # And manual_a3 will also be included.


# Hey! You see that CQRSPolymorphicSerializer superclass? **It is a lie.**
# CQRSSerializerMeta substitutes in its place the bases (ASerializer,
# ModelBAutoCQRSSerializer), derived from the ModelD bases. If it did not do
# that, then the inherited fields would not come through properly. Yes, this is
# immensely evil, but can you think of a better way to do it accurately? I
# repent in sackcloth and ashes, by the way. -- Chris Morgan
class DSerializer(CQRSPolymorphicSerializer):
    # Yes, this is *deliberately* calc_b3 and not calc_d3
    manual_d3 = CharField(source='calc_b3', max_length=12, read_only=True)

    class Meta:
        model = ModelD
        # This will then get the A and B serializers' fields added to it.
        fields = 'field_d1',


class CQRSTestCase(TestCase):
    def setUp(self):
        self.serializer = CQRSPolymorphicSerializer()

    def test_class_structures(self):
        a_s = CQRSSerializerMeta._register[ModelA]
        b_s = CQRSSerializerMeta._register[ModelB]
        c_s = CQRSSerializerMeta._register[ModelC]
        d_s = CQRSSerializerMeta._register[ModelD]

        self.assertIs(a_s, ASerializer)
        self.assertEqual(b_s.__name__, 'ModelBAutoCQRSSerializer')
        self.assertEqual(c_s.__name__, 'ModelCAutoCQRSSerializer')
        self.assertIs(d_s, DSerializer)

        self.assertEqual(a_s.Meta.__bases__, ())
        self.assertEqual(b_s.Meta.__bases__, (CQRSPolymorphicSerializer.Meta,
                                              object))
        self.assertEqual(c_s.Meta.__bases__, (a_s.Meta, b_s.Meta, object))
        # TODO(Chris): fix D serializer's bases; they should be the same as C's
        self.assertEqual(d_s.Meta.__bases__, ())

        common = {'type', 'id', 'mongoID'}
        self.assertEqual(set(a_s.Meta.fields),
                         common | {'field_a1', 'manual_a3'})
        self.assertEqual(set(b_s.Meta.fields),
                         common | {'field_b1', 'field_b2'})
        self.assertEqual(set(c_s.Meta.fields),
                         common | {'field_a1', 'manual_a3', 'field_b1',
                                   'field_b2', 'field_c1', 'field_c2'})
        self.assertEqual(set(d_s.Meta.fields),
                         common | {'field_a1', 'manual_a3', 'field_b1',
                                   'field_b2', 'field_d1', 'manual_d3'})

    def a(self):
        a = ModelA.objects.create(field_a1='a', field_a2='A')
        # Notable features: 'a2' is excluded, 'calc_a3' included, renamed
        return (a, {'type': 'cqrs.tests.ModelA',
                    'id': a.id,
                    'mongoID': a.mongoID,
                    'field_a1': 'a',
                    'manual_a3': 'from calc_a3'})

    def b(self):
        b = ModelB.objects.create(field_b1='b', field_b2='B')
        return (b, {'type': 'cqrs.tests.ModelB',
                    'id': b.id,
                    'mongoID': b.mongoID,
                    'field_b1': 'b',
                    'field_b2': 'B'})

    def c(self):
        c = ModelC.objects.create(field_a1='a', field_a2='A',
                                  field_b1='b', field_b2='B',
                                  field_c1='c', field_c2='C')
        return (c, {'type': 'cqrs.tests.ModelC',
                    'id': c.id,
                    'mongoID': c.mongoID,
                    'field_a1': 'a',
                    'manual_a3': 'from calc_a3',
                    'field_b1': 'b',
                    'field_b2': 'B',
                    'field_c1': 'c',
                    'field_c2': 'C'})

    def d(self):
        d = ModelD.objects.create(field_a1='a', field_a2='A',
                                  field_b1='b', field_b2='B',
                                  field_d1='d', field_d2='D')
        return (d, {'type': 'cqrs.tests.ModelD',
                    'id': d.id,
                    'mongoID': d.mongoID,
                    'field_a1': 'a',
                    'manual_a3': 'from calc_a3',
                    'field_b1': 'b',
                    'field_b2': 'B',
                    'field_d1': 'd',
                    'manual_d3': 'from calc_b3'})

    def test_a_serialize(self):
        a, a_serialized = self.a()
        self.assertEquals(self.serializer.to_native(a), a_serialized)

    def test_b_serialize(self):
        b, b_serialized = self.b()
        self.assertEqual(self.serializer.to_native(b), b_serialized)

    def test_c_serialize(self):
        c, c_serialized = self.c()
        self.assertEqual(self.serializer.to_native(c), c_serialized)

    def test_d_serialize(self):
        d, d_serialized = self.d()
        self.assertEqual(self.serializer.to_native(d), d_serialized)

    def deserialize(self, (model, serialized), ignore=()):
        deserialized = self.serializer.from_native(serialized)
        self.assertIsNot(deserialized, None,
                         'Deserialization of {!r} failed: {!r}'
                         .format(serialized, self.serializer.errors))
        deserialized = model_to_dict(deserialized)
        model = model_to_dict(model)
        for x in deserialized, model:
            for field in ignore:
                del x[field]
        self.assertEquals(deserialized, model)

    def test_a_deserialize(self):
        self.deserialize(self.a(), ('field_a2', 'id'))

    def test_b_deserialize(self):
        self.deserialize(self.b(), ('id',))

    def test_c_deserialize(self):
        # This is broken: mongoID is unaccountably lost in deserialization.
        # I haven't got any real idea why; I suspect it's to do with the
        # diamond inheritance in some way.
        self.deserialize(self.c(), ('field_a2', 'id',
                                    'modela_ptr', 'modelb_ptr'))

    def test_d_deserialize(self):
        # Similarly broken.
        self.deserialize(self.d(), ('field_a2', 'field_d2', 'id',
                                    'modela_ptr', 'modelb_ptr'))
