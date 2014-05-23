import re

from django.test import TestCase
from django.forms.models import model_to_dict

from ..models import CQRSPolymorphicModel
from ..serializers import CQRSPolymorphicSerializer, CQRSSerializerMeta

from .models import (ModelA, ModelAA, ModelAAA, ModelAAM, ModelAM, ModelAMA,
                     ModelAMM, ModelM, ModelMA, ModelMAA, ModelMAM, ModelMM,
                     ModelMMA, ModelMMM, AutomaticMixer, BoringModel,
                     OneMixingBowl, AnotherMixingBowl)
from .serializers import (AAMSerializer, AMSerializer, AMMSerializer,
                          MSerializer, MAMSerializer, MMSerializer,
                          MMMSerializer, BoringSerializer,
                          OneMixingBowlSerializer, AnotherMixingBowlSerializer)


def snakeify(cls):
    """Convert class __name__ into snake case: 'ClassName' -> 'class_name'"""
    return re.sub('(.)([A-Z])', r'\1_\2', cls.__name__).lower()


def make_nopoly_serialize_test_method(model):
    def new_test_method(self):
        instance = model.create_test_instance()
        serializer = CQRSSerializerMeta._register.instances[model]
        self.assertEqual(serializer.to_native(instance),
                         instance.as_test_serialized())

    new_test_method.__name__ = 'test_' + snakeify(model) + '_serialize'

    return new_test_method


def make_nopoly_structure_test_method(model_class, expect_serializer, fields):
    def new_test_method(self):
        serializer_class = CQRSSerializerMeta._register[model_class]
        self.assertEqual(serializer_class.Meta.__bases__, ())
        if isinstance(expect_serializer, str):
            self.assertEqual(serializer_class.__name__, expect_serializer)
        else:
            self.assertIs(serializer_class, expect_serializer)
        self.assertEqual(set(serializer_class().fields.keys()),
                            fields)
    new_test_method.__name__ = 'test_' + snakeify(model_class) + '_structure'

    return new_test_method


def make_nopoly_deserialize_test_method(model, fields_to_exclude):
    def new_test_method(self):
        instance = model.create_test_instance()
        # This is the *expected* value, not generated the regular way.
        serialized = instance.as_test_serialized()
        serializer = CQRSSerializerMeta._register[model]()

        deserialized = serializer.from_native(serialized, files=None)
        self.assertIsNot(deserialized, None,
                         'Deserialization of {!r} failed: {!r}'
                         .format(serialized, serializer.errors))

        # Turn them into dictionaries, so that we can compare them.
        deserialized = model_to_dict(deserialized)
        instance = model_to_dict(instance)

        # Now let's go through and remove some things which don't come through
        # serialization or deserialization and which thus can't be compared.
        for x in deserialized, instance:
            # ID is not deserialized.
            del x['id']

            for field in fields_to_exclude:
                del x[field]

        self.assertEqual(deserialized, instance)

    new_test_method.__name__ = 'test_' + snakeify(model) + '_deserialize'

    return new_test_method


def make_serialize_test_method(model):
    def new_test_method(self):
        instance = model.create_test_instance()
        self.assertEqual(self.serializer.to_native(instance),
                         instance.as_test_serialized())

    new_test_method.__name__ = 'test_' + model.prefix + '_serialize'

    return new_test_method


def make_deserialize_test_method(model):
    def new_test_method(self):
        instance = model.create_test_instance()
        # This is the *expected* value, not generated the regular way.
        serialized = instance.as_test_serialized()

        deserialized = self.serializer.from_native(serialized)
        self.assertIsNot(deserialized, None,
                         'Deserialization of {!r} failed: {!r}'
                         .format(serialized, self.serializer.errors))

        # Turn them into dictionaries, so that we can compare them.
        deserialized = model_to_dict(deserialized)
        instance = model_to_dict(instance)

        # Now let's go through and remove some things which don't come through
        # serialization or deserialization and which thus can't be compared.
        for x in deserialized, instance:

            # ID is not deserialized.
            del x['id']

            # The second field from any manual serializer in the hierarchy,
            # because they aren't included in the serializer.
            for base in model.__mro__:
                if base is CQRSPolymorphicModel:
                    break
                assert base.__name__.startswith('Model')
                if base.prefix.endswith('m'):  # Manual serializer
                    del x['field_{}2'.format(base.prefix)]
                if base is not model:
                    # Remove the (unserialized) foreign keys to the base also.
                    del x['{}_ptr'.format(base.__name__.lower())]

        self.assertEqual(deserialized, instance)

    new_test_method.__name__ = 'test_' + model.prefix + '_deserialize'

    return new_test_method


class NonPolymorphicSerializersTestCase(TestCase):

    for model, fields_to_exclude in (
            (BoringModel, ('roses',)),
            (OneMixingBowl, ('flour', 'oil')),
            (AnotherMixingBowl, ()),
            (AutomaticMixer, ())):
        f = make_nopoly_deserialize_test_method(model, fields_to_exclude)
        locals()[f.__name__] = f
        f = make_nopoly_serialize_test_method(model)
        locals()[f.__name__] = f

    for model, expect_serializer, fields in (
            (BoringModel, BoringSerializer,
                {'id', 'violets', 'daft_poem'}),
            (OneMixingBowl, OneMixingBowlSerializer,
                {'id', 'sugar', 'water', 'total'}),
            (AnotherMixingBowl, AnotherMixingBowlSerializer,
                {'id', 'sugar', 'flour', 'water', 'oil'}),
            (AutomaticMixer, 'AutomaticMixerAutoCQRSSerializer',
                {'id', 'sugar', 'flour'})):
        f = make_nopoly_structure_test_method(model, expect_serializer, fields)
        locals()[f.__name__] = f


class PolymorphicSerializersTestCase(TestCase):

    def setUp(self):
        self.serializer = CQRSPolymorphicSerializer()

    for model in (ModelA, ModelAA, ModelAAA, ModelAAM, ModelAM, ModelAMA,
                  ModelAMM, ModelM, ModelMA, ModelMAA, ModelMAM, ModelMM,
                  ModelMMA, ModelMMM):
        f = make_deserialize_test_method(model)
        locals()[f.__name__] = f
        f = make_serialize_test_method(model)
        locals()[f.__name__] = f
    del f

    def test_class_structures(self):
        s_a = CQRSSerializerMeta._register[ModelA]
        s_aa = CQRSSerializerMeta._register[ModelAA]
        s_aaa = CQRSSerializerMeta._register[ModelAAA]
        s_aam = CQRSSerializerMeta._register[ModelAAM]
        s_am = CQRSSerializerMeta._register[ModelAM]
        s_ama = CQRSSerializerMeta._register[ModelAMA]
        s_amm = CQRSSerializerMeta._register[ModelAMM]
        s_m = CQRSSerializerMeta._register[ModelM]
        s_ma = CQRSSerializerMeta._register[ModelMA]
        s_maa = CQRSSerializerMeta._register[ModelMAA]
        s_mam = CQRSSerializerMeta._register[ModelMAM]
        s_mm = CQRSSerializerMeta._register[ModelMM]
        s_mma = CQRSSerializerMeta._register[ModelMMA]
        s_mmm = CQRSSerializerMeta._register[ModelMMM]

        self.assertEqual(s_a.__name__, 'ModelAAutoCQRSSerializer')
        self.assertEqual(s_aa.__name__, 'ModelAAAutoCQRSSerializer')
        self.assertEqual(s_aaa.__name__, 'ModelAAAAutoCQRSSerializer')
        self.assertIs(s_aam, AAMSerializer)
        self.assertIs(s_am, AMSerializer)
        self.assertEqual(s_ama.__name__, 'ModelAMAAutoCQRSSerializer')
        self.assertIs(s_amm, AMMSerializer)
        self.assertIs(s_m, MSerializer)
        self.assertEqual(s_ma.__name__, 'ModelMAAutoCQRSSerializer')
        self.assertEqual(s_maa.__name__, 'ModelMAAAutoCQRSSerializer')
        self.assertIs(s_mam, MAMSerializer)
        self.assertIs(s_mm, MMSerializer)
        self.assertEqual(s_mma.__name__, 'ModelMMAAutoCQRSSerializer')
        self.assertIs(s_mmm, MMMSerializer)

        self.assertEqual(s_a.Meta.__bases__, ())
        self.assertEqual(s_aa.Meta.__bases__, ())
        self.assertEqual(s_aaa.Meta.__bases__, ())
        self.assertEqual(s_aam.Meta.__bases__, ())
        self.assertEqual(s_am.Meta.__bases__, ())
        self.assertEqual(s_ama.Meta.__bases__, ())
        self.assertEqual(s_amm.Meta.__bases__, ())
        self.assertEqual(s_m.Meta.__bases__, ())
        self.assertEqual(s_ma.Meta.__bases__, ())
        self.assertEqual(s_maa.Meta.__bases__, ())
        self.assertEqual(s_mam.Meta.__bases__, ())
        self.assertEqual(s_mm.Meta.__bases__, ())
        self.assertEqual(s_mma.Meta.__bases__, ())
        self.assertEqual(s_mmm.Meta.__bases__, ())

        common = {'type', 'id'}
        self.assertEqual(set(s_a().fields.keys()),
                         common | {'field_a1', 'field_a2',
                                   })
        self.assertEqual(set(s_aa().fields.keys()),
                         common | {'field_a1', 'field_a2',
                                   'field_aa1', 'field_aa2',
                                   })
        self.assertEqual(set(s_aaa().fields.keys()),
                         common | {'field_a1', 'field_a2',
                                   'field_aa1', 'field_aa2',
                                   'field_aaa1', 'field_aaa2',
                                   })
        self.assertEqual(set(s_aam().fields.keys()),
                         common | {'field_a1', 'field_a2',
                                   'field_aa1', 'field_aa2',
                                   'field_aam1', 'manual_aam3',
                                   })
        self.assertEqual(set(s_am().fields.keys()),
                         common | {'field_a1', 'field_a2',
                                   'field_am1', 'manual_am3',
                                   })
        self.assertEqual(set(s_ama().fields.keys()),
                         common | {'field_a1', 'field_a2',
                                   'field_am1', 'manual_am3',
                                   'field_ama1', 'field_ama2',
                                   })
        self.assertEqual(set(s_amm().fields.keys()),
                         common | {'field_a1', 'field_a2',
                                   'field_am1', 'manual_am3',
                                   'field_amm1', 'manual_amm3',
                                   })
        self.assertEqual(set(s_m().fields.keys()),
                         common | {'field_m1', 'manual_m3',
                                   })
        self.assertEqual(set(s_ma().fields.keys()),
                         common | {'field_m1', 'manual_m3',
                                   'field_ma1', 'field_ma2',
                                   })
        self.assertEqual(set(s_maa().fields.keys()),
                         common | {'field_m1', 'manual_m3',
                                   'field_ma1', 'field_ma2',
                                   'field_maa1', 'field_maa2',
                                   })
        self.assertEqual(set(s_mam().fields.keys()),
                         common | {'field_m1', 'manual_m3',
                                   'field_ma1', 'field_ma2',
                                   'field_mam1', 'manual_mam3',
                                   })
        self.assertEqual(set(s_mm().fields.keys()),
                         common | {'field_m1', 'manual_m3',
                                   'field_mm1', 'manual_mm3',
                                   })
        self.assertEqual(set(s_mma().fields.keys()),
                         common | {'field_m1', 'manual_m3',
                                   'field_mm1', 'manual_mm3',
                                   'field_mma1', 'field_mma2',
                                   })
        self.assertEqual(set(s_mmm().fields.keys()),
                         common | {'field_m1', 'manual_m3',
                                   'field_mm1', 'manual_mm3',
                                   'field_mmm1', 'manual_mmm3',
                                   })
