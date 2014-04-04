from django.test import TestCase

from ..models import CQRSModel, CQRSPolymorphicModel
from ..collections import (DRFPolymorphicDocumentCollection,
                           DRFDocumentCollection,
                           SubCollection, SubCollectionMeta)

from .models import (ModelA, ModelAA, ModelAAA, ModelAAM, ModelAM, ModelAMA,
                     ModelAMM, ModelM, ModelMA, ModelMAA, ModelMAM, ModelMM,
                     ModelMMA, ModelMMM)
#from .serializers import (AAMSerializer, AMSerializer, AMMSerializer,
#                          MSerializer, MAMSerializer, MMSerializer,
#                          MMMSerializer)
from .collections import (ACollection, MCollection, AMSubCollection,
                          AMMSubCollection, MAMSubCollection)


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
