import logging
import pymongo
import importlib

from bson.objectid import ObjectId

from django.conf import settings
from django.db.models.fields.related import ForeignRelatedObjectsDescriptor
from denormalize.backend.mongodb import MongoBackend
from denormalize.models import DocumentCollection


logger = logging.getLogger(__name__)


REA_MODEL_DATA_COLLECTION_NAME = getattr(settings,
    "REA_MODEL_DATA_COLLECTION_NAME", "model_data")
REA_MONGO_DB_NAME = getattr(settings,
    "REA_MONGO_DB_NAME", "rea_denormalized")
REA_MONGO_CONNECTION_URI = getattr(settings,
    "REA_MONGO_URI", "mongodb://localhost")


def import_from_string(string):
    mods = string.split('.')
    class_str = mods[-1]
    path_str = '.'.join(mods[:-1])
    module = importlib.import_module(path_str)
    return getattr(module, class_str)


class REAMongoBackend(MongoBackend):
    db_name = "test_denormalize"

    def get_mongo_id(self, collection, doc_id):
        return collection.model.objects.get(id=doc_id).mongoID

    def connect(self):
        self.connection = pymongo.Connection(self.connection_uri, safe=True)
        self.db = getattr(self.connection, self.db_name)

        # Remove all model data from mongo, to be replaced in _setup_listeners
        self.db[REA_MODEL_DATA_COLLECTION_NAME].remove()


    def get_parent_table_name(self, collection, table_name):
        return "%s__%s" % (
            collection.parent_collection.name,
            table_name
        )

    def deleted(self, collection, doc_id):
        mongoID = self.get_mongo_id(collection, doc_id)
        current_collection = collection
        while True:
            has_parent = False
            table_name = current_collection.name
            if current_collection.parent_collection:
                table_name = self.get_parent_table_name(
                    current_collection, table_name
                )
                has_parent = True

            logging.debug('deleted: %s %s', current_collection.name, doc_id)
            col = getattr(self.db, current_collection.name)
            col.remove({'_id': mongoID})

            if not has_parent:
                break
            current_collection = current_collection.parent_collection

    def added(self, collection, doc_id, doc):
        # We can share the same ID across
        mongoID = self.get_mongo_id(collection, doc_id)
        is_parent = True
        parent_table_name = collection.name
        current_collection = collection
        while True:
            has_parent = False
            table_name = current_collection.name
            if current_collection.parent_collection:
                table_name = self.get_parent_table_name(
                    current_collection, table_name
                )
                has_parent = True

            logging.debug('added: %s %s', table_name, doc_id)
            col = getattr(self.db, table_name)
            # Replace any existing document
            doc['_id'] = mongoID
            if not is_parent:
                doc['_parent_table'] = parent_table_name
            col.update({'_id': mongoID}, doc, upsert=True)

            if not has_parent:
                break
            current_collection = current_collection.parent_collection
            is_parent = False

    def changed(self, collection, doc_id, doc):
        mongoID = self.get_mongo_id(collection, doc_id)
        current_collection = collection

        while True:
            has_parent = False
            table_name = current_collection.name
            if current_collection.parent_collection:
                table_name = self.get_parent_table_name(
                    current_collection, table_name
                )
                has_parent = True

            logging.debug('changed: %s %s', current_collection.name, doc_id)
            col = getattr(self.db, table_name)
            # We are not allowed to update _id
            if '_id' in doc:
                del doc['_id']
            # Only update the documents fields. We keep any other fields
            # added by other code intact, as long as they are set on the
            # document root.
            col.update({'_id': mongoID}, {'$set': doc}, upsert=True)

            if not has_parent:
                break
            current_collection = current_collection.parent_collection

        # WARNING: Code is evil (in this state)
        # ---------------------------------------------------
        serializer_class = collection.serializer_class
        model = serializer_class.Meta.model
        model_instance = model.objects.get(id=doc_id)

        # Get a list of reverse foreign keys our model could have
        if isinstance(serializer_class, str):
            serializer_class = import_from_string(serializer_class)
        reversed_f_keys = [
            attr for attr in model.__dict__.values()
            if isinstance(attr, ForeignRelatedObjectsDescriptor)
        ]

        # TODO: Why is customer being saved twice?
        for f_key in reversed_f_keys:
            # Get the reverse lookup model manager
            reverse_lookup = getattr(
                model_instance, f_key.related.get_accessor_name())

            # Check to see if the model is part of the mongo collection
            # saving process
            _collection = [
                x for x in self.collections.values()
                if x.model == reverse_lookup.model
            ]

            if len(_collection):
                col = _collection[0]

                # Loop through any parent collections and apply changes
                # to polymorphic tables and reverse lookups
                while col is not None:
                    document_ids = reverse_lookup.values_list('id', flat=True)
                    for d_id in document_ids:
                        # Update each document that has a link to the current
                        # model
                        self._call_changed(col, d_id)

                    if col.parent_collection:
                        # Get the parent collection from the registered
                        # collections list and loop again
                        _sub_collection = [
                            x for x in self.collections.values()
                            if x.model == col.parent_collection.model
                        ]
                        if len(_sub_collection):
                            col = _sub_collection[0]
                            continue
                    col = None


    def get_doc(self, collection, doc_id):
        mongoID = self.get_mongo_id(collection, doc_id)
        col = getattr(self.db, collection.name)
        return col.find_one({'_id': mongoID})


    def _setup_listeners(self, collection):
        """
        Add a model type dictionary for our models
        """
        super(REAMongoBackend, self)._setup_listeners(collection)

        serializer_class = collection.serializer_class
        if isinstance(serializer_class, str):
            serializer_class = import_from_string(serializer_class)

        serialized_fields = [
            x for x in collection.model._meta.fields
            if x.name in serializer_class.Meta.fields

        ]

        names = [x.name for x in serialized_fields]
        types = [x.get_internal_type() for x in serialized_fields]
        data = dict(zip(names, types))
        data['_id'] = str(ObjectId())

        current_collection = collection
        table_name = current_collection.name
        # Currently a TOTAL copy of a method above. Refactor this
        while True:
            has_parent = False
            if current_collection.parent_collection:
                table_name = self.get_parent_table_name(
                    current_collection, table_name
                )
                has_parent = True

            if not has_parent:
                break
            current_collection = current_collection.parent_collection

        data['_collection'] = table_name
        self.db[REA_MODEL_DATA_COLLECTION_NAME].insert(data)


mongodb = REAMongoBackend(
    name='mongo',
    db_name=REA_MONGO_DB_NAME,
    connection_uri=REA_MONGO_CONNECTION_URI
)


class DRFDocumentCollection(DocumentCollection):
    """
    Overrides `DocumentCollection` to make use of the Django Rest Framework
    serializer for serializing our objects. This provides more power in
    what data we want to retrieve.

    TODO: How to deal with stale foreign key data being cached in mongo?
    """
    serializer_class = None

    # Parent DRFDocumentCollection (for saving child objects)
    parent_collection = None

    def __init__(self):
        if self.serializer_class is None:
            raise ValueError("serializer_class can not be None")
        if self.model is None:
            self.model = self.serializer_class.Meta.model
        if not self.name:
            self.name = self.model._meta.db_table

    def get_related_models(self):
        """
        Override the get_related_models to disable the function. This will
        be done with Django Rest Framework instead
        """
        return {}

    def dump_obj(self, model, obj, path):
        """
        Use Django Rest Framework to serialize our object
        """
        if isinstance(self.serializer_class, str):
            self.serializer_class = import_from_string(self.serializer_class)

        data = self.serializer_class(obj).data
        logger.debug('\033[94m%s:\033[0m %s' % (model._meta.db_table, data))
        return data
