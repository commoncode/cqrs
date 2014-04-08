from django.test import TestCase

from ..models import CQRSModel, CQRSPolymorphicModel
from ..collections import (DRFPolymorphicDocumentCollection,
                           DRFDocumentCollection,
                           SubCollection, SubCollectionMeta)

from .models import (ModelA, ModelAA, ModelAAA, ModelAAM, ModelAM, ModelAMA,
                     ModelAMM, ModelM, ModelMA, ModelMAA, ModelMAM, ModelMM,
                     ModelMMA, ModelMMM, BoringModel, OneMixingBowl,
                     AnotherMixingBowl, AutomaticMixer)
from .collections import (ACollection, MCollection, AMSubCollection,
                          AMMSubCollection, MAMSubCollection, BoringCollection,
                          OneMixingBowlCollection, AnotherMixingBowlCollection,
                          AutomaticMixerCollection)
from .backend import OpLogBackend, Action, ADD, DELETE, CHANGE


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


class JustCollectionTests(TestCase):
    '''Tests for Collections in the absense of a backend.'''

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

    def test_collection_name(self):
        self.assertEqual(ACollection().name, 'cqrs_modela')
        self.assertEqual(MCollection().name, 'cqrs_modelm')

    def test_subcollection_name_unimplemented(self):
        # Subcollections take their base collection's name, but only if it's
        # specified manually, for the moment.
        subcollection = SubCollectionMeta._register[ModelAAA]()
        with self.assertRaises(NotImplementedError):
            # This test is in so that if it is actually implemented you'll go
            # writing tests for it.
            subcollection.name

    def test_subcollection_name_from_base_collection(self):
        subcollection = SubCollectionMeta._register[ModelAAA]()
        # Not sure whether this should be a class or an instance, really, but
        # because we're using property at present it needs to be an instance.
        # Of course, you can make a classproperty with descriptors, but this is
        # stuff that I don't know whether it's needed anyway, so I'm not going
        # overboard with implementing complex things; I'm only going overboard
        # in writing all these crazy comments.
        subcollection.base_collection = ACollection()
        self.assertEqual(subcollection.name, 'cqrs_modela')

    def test_bad_drf_document_collection_instantiation(self):
        # The idea here is to show that yes, you do need to create a collection
        # class; it's not like ``CQRSPolymorphicSerializer()``
        for cls in (DRFDocumentCollection, DRFPolymorphicDocumentCollection,
                    SubCollection):
            with self.assertRaises(NotImplementedError) as r:
                cls()
            self.assertEqual(r.exception.message, 'Document.model not set')

    def test_non_polymorphic_collection_on_polymorphic_model(self):
        class PollyWantAModel(CQRSPolymorphicModel):
            pass

        with self.assertRaises(TypeError) as r:
            class PollyWantACollection(DRFDocumentCollection):
                model = PollyWantAModel

        self.assertEqual(r.exception.message,
                         "type 'PollyWantACollection' uses model "
                         "'PollyWantAModel' which is derived from "
                         "'CQRSPolymorphicModel' (not a permitted base)")

    def test_polymorphic_collection_on_non_polymorphic_model(self):
        class UntitledModel(CQRSModel):
            pass

        with self.assertRaises(TypeError) as r:
            class UntitledCollection(DRFPolymorphicDocumentCollection):
                model = UntitledModel

        self.assertEqual(r.exception.message,
                         "type 'UntitledCollection' uses model 'UntitledModel'"
                         " which is not derived from 'CQRSPolymorphicModel'")


def make_test_method(model, name=None):
    def new_test_method(self):
        if model.prefix.startswith('m'):
            collection = self.m_collection
        else:
            collection = self.a_collection

        field_base = 'field_{}1'.format(model.prefix[0])
        field_sub = 'field_{}1'.format(model.prefix)

        # Test creation
        obj = model.create_test_instance()
        doc = obj.as_test_serialized()
        self.assertEqual(self.backend.flush_oplog(),
                        [Action(action=ADD, collection=collection,
                                doc_id=obj.id, doc=doc)])

        # Test changing a *parent* [except it's not for the bases] attribute
        setattr(obj, field_base, 'changed')
        doc[field_base] = 'changed'
        obj.save()
        self.assertEqual(self.backend.flush_oplog(),
                        [Action(action=CHANGE, collection=collection,
                                doc_id=obj.id, doc=doc)])

        # Test changing *my* attribute
        setattr(obj, field_sub, 'changed')
        doc[field_sub] = 'changed'
        obj.save()
        self.assertEqual(self.backend.flush_oplog(),
                        [Action(action=CHANGE, collection=collection,
                                doc_id=obj.id, doc=doc)])

        # Test changing both (to ensure the signal is only triggered once)
        setattr(obj, field_base, 'new value')
        doc[field_base] = 'new value'
        setattr(obj, field_sub, 'new value')
        doc[field_sub] = 'new value'
        obj.save()
        self.assertEqual(self.backend.flush_oplog(),
                        [Action(action=CHANGE, collection=collection,
                                doc_id=obj.id, doc=doc)])

        # Test deletion
        doc_id = obj.id
        obj.delete()
        self.assertEqual(self.backend.flush_oplog(),
                        [Action(action=DELETE, collection=collection,
                                doc_id=doc_id, doc=None)])

    if name is None:
        new_test_method.__name__ = 'test_model{}_signals'.format(model.prefix)
    else:
        new_test_method.__name__ = name

    return new_test_method

class CollectionAndBackendTests(TestCase):
    """Tests for collections and how they interact with a backend."""

    @classmethod
    def setUpClass(cls):
        cls.backend = OpLogBackend(name='collection_and_backend_tests')
        cls.a_collection = ACollection()
        cls.m_collection = MCollection()
        cls.boring_collection = BoringCollection()
        cls.one_mixing_bowl_collection = OneMixingBowlCollection()
        cls.another_mixing_bowl_collection = AnotherMixingBowlCollection()
        cls.automatic_mixer_collection = AutomaticMixerCollection()
        cls.backend.register(cls.a_collection)
        cls.backend.register(cls.m_collection)
        cls.backend.register(cls.boring_collection)
        cls.backend.register(cls.one_mixing_bowl_collection)
        cls.backend.register(cls.another_mixing_bowl_collection)
        cls.backend.register(cls.automatic_mixer_collection)

    def setUp(self):
        # Ensure we have a clean oplog for each test.
        self.backend.flush_oplog()

    def tearDown(self):
        # There should not be anything in the oplog at the end of a test.
        self.assertEqual(self.backend.flush_oplog(), [])

    for model, name in (
            (ModelA, 'test_base_polymorphic_model_with_automatic_serializer'),
            (ModelM, 'test_base_polymorphic_model_with_manual_serializer')):
        f = make_test_method(model, name)
        locals()[f.__name__] = f

    for model in (ModelA, ModelAA, ModelAAA, ModelAAM, ModelAM, ModelAMA,
                  ModelAMM, ModelM, ModelMA, ModelMAA, ModelMAM, ModelMM,
                  ModelMMA, ModelMMM):
        f = make_test_method(model)
        locals()[f.__name__] = f

    def do_test_on_thingies(self, collection, model, update_function):
        # Test creation
        obj = model.create_test_instance()
        doc = obj.as_test_serialized()
        self.assertEqual(self.backend.flush_oplog(),
                        [Action(action=ADD, collection=collection,
                                doc_id=obj.id, doc=doc)])

        # Test changing an attribute
        update_function(obj, doc)
        obj.save()
        self.assertEqual(self.backend.flush_oplog(),
                        [Action(action=CHANGE, collection=collection,
                                doc_id=obj.id, doc=doc)])

        # Test deletion
        doc_id = obj.id
        obj.delete()
        self.assertEqual(self.backend.flush_oplog(),
                        [Action(action=DELETE, collection=collection,
                                doc_id=doc_id, doc=None)])

    def test_non_polymorphic_model_collection(self):
        def update(obj, doc):
            obj.violets = doc['violets'] = 'green'
            doc['daft_poem'] = obj.silly_poetry()
        self.do_test_on_thingies(self.boring_collection, BoringModel, update)

    def test_non_polymorphic_model_collection_with_mixin_and_serializer(self):
        def update(obj, doc):
            obj.water = doc['water'] = 200
            doc['total'] = obj.total
        self.do_test_on_thingies(self.one_mixing_bowl_collection,
                                 OneMixingBowl, update)

    def test_non_polymorphic_model_collection_with_mixin_and_partial_serializer(self):
        def update(obj, doc):
            obj.water = doc['water'] = 200
        self.do_test_on_thingies(self.another_mixing_bowl_collection,
                                 AnotherMixingBowl, update)

    # Can't do anything with AutomaticMixer, because it can't have a serializer
    # created (see test_serializers)
