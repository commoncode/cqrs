from . import settings
from .backend import PolymorphicBackendBase

from denormalize.backend.mongodb import MongoBackend


class PolymorphicMongoBackend(MongoBackend, PolymorphicBackendBase):
    pass


mongodb = PolymorphicMongoBackend(
    name='mongo',
    db_name=settings.CQRS_MONGO_DB_NAME,
    connection_uri=settings.CQRS_MONGO_CONNECTION_URI
)
