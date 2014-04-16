from . import settings
from .backend import PolymorphicBackendBase

from denormalize.backend.mongodb import MongoBackend


class MongoIDBackend(MongoBackend):

    def added(self, collection, doc_id, doc):
        doc['_id'] = doc.pop('id')
        super(MongoIDBackend, self).added(collection, doc_id, doc)

    def changed(self, collection, doc_id, doc):
        doc['_id'] = doc.pop('id')
        super(MongoIDBackend, self).changed(collection, doc_id, doc)


class PolymorphicMongoIDBackend(MongoIDBackend, PolymorphicBackendBase):
    pass


mongodb = PolymorphicMongoIDBackend(
    name='mongo',
    db_name=settings.CQRS_MONGO_DB_NAME,
    connection_uri=settings.CQRS_MONGO_CONNECTION_URI
)
