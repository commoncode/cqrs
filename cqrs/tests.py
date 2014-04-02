from django.db import models
from django.test import TestCase
from django.forms.models import model_to_dict
from rest_framework.fields import CharField
from .models import CQRSPolymorphicModel
from .serializers import CQRSPolymorphicSerializer, CQRSSerializerMeta
from .collections import (DRFDocumentCollection,
                          SubCollection, SubCollectionMeta)


# Gener
def make(prefix, base):
    '''
    Generate things.

    Usage::

        ModelAA = make('aa', ModelA)

    This is equivalent to::

        class ModelAA(ModelA):
            field_aa1 = models.CharField(max_length=50)
            field_aa2 = models.CharField(max_length=50)

            def calc_aa3(self):
                return 'from calc_aa3'
    '''

    @classmethod
    def test_data(cls, model_instance=None):
        '''
        Produce a dictionary of the test data, in serialized form if a
        model instance is given (representing what it is expected
        serializing the instance will yield), or as the keyword arguments
        for ``Model.objects.create()`` if no instance is given.
        '''
        fields = {}
        for base in cls.__mro__:
            if base is CQRSPolymorphicModel:
                break
            assert base.__name__.startswith('Model')
            fields['field_{}1'.format(base.prefix)] = base.prefix
            if base.prefix.endswith('m'):  # Manual serializer
                if model_instance:
                    fields['manual_{}3'.format(base.prefix)] = \
                        'from calc_{}3'.format(base.prefix)
            else:  # Automatic serializer
                fields['field_{}2'.format(base.prefix)] = base.prefix.upper()
        if model_instance:
            fields['id'] = model_instance.id
            fields['mongoID'] = model_instance.mongoID
            fields['type'] = '{}.{}'.format(type(model_instance).__module__,
                                            type(model_instance).__name__)
        return fields

    def as_test_serialized(self):
        return self.test_data(self)

    @classmethod
    def create_test_instance(cls):
        return cls.objects.create(**cls.test_data())

    return type(base)(
        'Model' + prefix.upper(),
        (base,),
        {
            'field_{}1'.format(prefix): models.CharField(max_length=50),
            'field_{}2'.format(prefix): models.CharField(max_length=50),
            'calc_{}3'.format(prefix): lambda self: \
                                       'from calc_{}3'.format(prefix),
            'prefix': prefix,
            'test_data': test_data,
            'as_test_serialized': as_test_serialized,
            'create_test_instance': create_test_instance,
            '__module__': __name__,
        })


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
        fields = 'field_{}1'.format(model.prefix),

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


# Naming scheme: ending with 'A' means the serializer for that class is
# automatic, and with 'M' means there is a manually specified serializer.
# We'll go down to three levels; that should take care of everything.
ModelA   = make('a',   CQRSPolymorphicModel)
ModelAA  = make('aa',  ModelA)
ModelAAA = make('aaa', ModelAA)
ModelAAM = make('aam', ModelAA)
ModelAM  = make('am',  ModelA)  # good morning
ModelAMA = make('ama', ModelAM)
ModelAMM = make('amm', ModelAM)
ModelM   = make('m',   CQRSPolymorphicModel)
ModelMA  = make('ma',  ModelM)
ModelMAA = make('maa', ModelMA)
ModelMAM = make('mam', ModelMA)
ModelMM  = make('mm',  ModelM)
ModelMMA = make('mma', ModelMM)
ModelMMM = make('mmm', ModelMM)

AAMSerializer = make_serializer(ModelAAM)
AMSerializer  = make_serializer(ModelAM)
AMMSerializer = make_serializer(ModelAMM)
MSerializer   = make_serializer(ModelM)
MAMSerializer = make_serializer(ModelMAM)
MMSerializer  = make_serializer(ModelMM)
MMMSerializer = make_serializer(ModelMMM)


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
        for model in (ModelA, ModelAA, ModelAAA, ModelAAM, ModelAM, ModelAMA,
                      ModelAMM, ModelM, ModelMA, ModelMAA, ModelMAM, ModelMM,
                      ModelMMA, ModelMMM):
            pass

        s_a   = CQRSSerializerMeta._register[ModelA]
        s_aa  = CQRSSerializerMeta._register[ModelAA]
        s_aaa = CQRSSerializerMeta._register[ModelAAA]
        s_aam = CQRSSerializerMeta._register[ModelAAM]
        s_am  = CQRSSerializerMeta._register[ModelAM]
        s_ama = CQRSSerializerMeta._register[ModelAMA]
        s_amm = CQRSSerializerMeta._register[ModelAMM]
        s_m   = CQRSSerializerMeta._register[ModelM]
        s_ma  = CQRSSerializerMeta._register[ModelMA]
        s_maa = CQRSSerializerMeta._register[ModelMAA]
        s_mam = CQRSSerializerMeta._register[ModelMAM]
        s_mm  = CQRSSerializerMeta._register[ModelMM]
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

        # At present, manually specified Meta classes don't get their bases
        # changed to straighten out inheritance. Perhaps they should, perhaps
        # they shouldn't. Django doesn't by default.
        self.assertEqual(s_a.Meta.__bases__, (CQRSPolymorphicSerializer.Meta,
                                              object))
        self.assertEqual(s_aa.Meta.__bases__, (s_a.Meta, object))
        self.assertEqual(s_aaa.Meta.__bases__, (s_aa.Meta, object))
        self.assertEqual(s_aam.Meta.__bases__, ())
        self.assertEqual(s_am.Meta.__bases__, ())
        self.assertEqual(s_ama.Meta.__bases__, (s_am.Meta, object))
        self.assertEqual(s_amm.Meta.__bases__, ())
        self.assertEqual(s_m.Meta.__bases__, ())
        self.assertEqual(s_ma.Meta.__bases__, (s_m.Meta, object))
        self.assertEqual(s_maa.Meta.__bases__, (s_ma.Meta, object))
        self.assertEqual(s_mam.Meta.__bases__, ())
        self.assertEqual(s_mm.Meta.__bases__, ())
        self.assertEqual(s_mma.Meta.__bases__, (s_mm.Meta, object))
        self.assertEqual(s_mmm.Meta.__bases__, ())

        common = {'type', 'id', 'mongoID'}
        self.assertEqual(set(s_a.Meta.fields),
                         common | {'field_a1', 'field_a2',
                                   })
        self.assertEqual(set(s_aa.Meta.fields),
                         common | {'field_a1', 'field_a2',
                                   'field_aa1', 'field_aa2',
                                   })
        self.assertEqual(set(s_aaa.Meta.fields),
                         common | {'field_a1', 'field_a2',
                                   'field_aa1', 'field_aa2',
                                   'field_aaa1', 'field_aaa2',
                                   })
        self.assertEqual(set(s_aam.Meta.fields),
                         common | {'field_a1', 'field_a2',
                                   'field_aa1', 'field_aa2',
                                   'field_aam1', 'manual_aam3',
                                   })
        self.assertEqual(set(s_am.Meta.fields),
                         common | {'field_a1', 'field_a2',
                                   'field_am1', 'manual_am3',
                                   })
        self.assertEqual(set(s_ama.Meta.fields),
                         common | {'field_a1', 'field_a2',
                                   'field_am1', 'manual_am3',
                                   'field_ama1', 'field_ama2',
                                   })
        self.assertEqual(set(s_amm.Meta.fields),
                         common | {'field_a1', 'field_a2',
                                   'field_am1', 'manual_am3',
                                   'field_amm1', 'manual_amm3',
                                   })
        self.assertEqual(set(s_m.Meta.fields),
                         common | {'field_m1', 'manual_m3',
                                   })
        self.assertEqual(set(s_ma.Meta.fields),
                         common | {'field_m1', 'manual_m3',
                                   'field_ma1', 'field_ma2',
                                   })
        self.assertEqual(set(s_maa.Meta.fields),
                         common | {'field_m1', 'manual_m3',
                                   'field_ma1', 'field_ma2',
                                   'field_maa1', 'field_maa2',
                                   })
        self.assertEqual(set(s_mam.Meta.fields),
                         common | {'field_m1', 'manual_m3',
                                   'field_ma1', 'field_ma2',
                                   'field_mam1', 'manual_mam3',
                                   })
        self.assertEqual(set(s_mm.Meta.fields),
                         common | {'field_m1', 'manual_m3',
                                   'field_mm1', 'manual_mm3',
                                   })
        self.assertEqual(set(s_mma.Meta.fields),
                         common | {'field_m1', 'manual_m3',
                                   'field_mm1', 'manual_mm3',
                                   'field_mma1', 'field_mma2',
                                   })
        self.assertEqual(set(s_mmm.Meta.fields),
                         common | {'field_m1', 'manual_m3',
                                   'field_mm1', 'manual_mm3',
                                   'field_mmm1', 'manual_mmm3',
                                   })


class ACollection(DRFDocumentCollection):
    # Yeah, I know A was for automatic. But this one can't be automatic (it's
    # the collection, only subcollections can be done automatically).
    model = ModelA


class MCollection(DRFDocumentCollection):
    model = ModelM


# Good morning (again).
class AMSubCollection(SubCollection):
    model = ModelAM


class AMMSubCollection(SubCollection):
    model = ModelAMM


class MAMSubCollection(SubCollection):
    model = ModelMAM


def make_collection_test_method(model):
    def new_test_method(self):
        if model.prefix.startswith('a'):
            collection = ACollection()
        else:
            collection = MCollection()
        instance = model.create_test_instance()
        self.assertEqual(collection.dump(instance),
                         instance.as_test_serialized())

    new_test_method.__name__ = 'test_' + model.prefix + '_dump'

    return new_test_method


class CollectionTests(TestCase):

    for model in (ModelA, ModelAA, ModelAAA, ModelAAM, ModelAM, ModelAMA,
                  ModelAMM, ModelM, ModelMA, ModelMAA, ModelMAM, ModelMM,
                  ModelMMA, ModelMMM):
        f = make_collection_test_method(model)
        locals()[f.__name__] = f
    del f

    def test_class_structures(self):

        c_am = SubCollectionMeta._register[ModelAM]
        c_amm = SubCollectionMeta._register[ModelAMM]
        c_mam = SubCollectionMeta._register[ModelMAM]
        c_ma = SubCollectionMeta._register[ModelMA]
        c_ama = SubCollectionMeta._register[ModelAMA]
        c_aaa = SubCollectionMeta._register[ModelAAA]

        self.assertIs(c_am, AMSubCollection)
        self.assertIs(c_amm, AMMSubCollection)
        self.assertIs(c_mam, MAMSubCollection)
        self.assertEqual(c_ma.__name__, 'ModelMAAutoSubCollection')
        self.assertEqual(c_ama.__name__, 'ModelAMAAutoSubCollection')
        self.assertEqual(c_aaa.__name__, 'ModelAAAAutoSubCollection')

    def test_bad_drf_document_collection_instantiation(self):
        # The idea here is to show that yes, you do need to create a collection
        # class; it's not like ``CQRSPolymorphicSerializer()``
        with self.assertRaises(NotImplementedError) as r:
            DRFDocumentCollection()
        self.assertEqual(r.exception.message, 'Document.model not set')
