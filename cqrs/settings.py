'''CQRS-specific settings.'''
from django.conf import settings


CQRS_MODEL_DATA_COLLECTION_NAME = getattr(
    settings, "CQRS_MODEL_DATA_COLLECTION_NAME", "model_data")

CQRS_MONGO_DB_NAME = getattr(
    settings, "CQRS_MONGO_DB_NAME", "cqrs_denormalized")

CQRS_MONGO_CONNECTION_URI = getattr(
    settings, "CQRS_MONGO_URI", "mongodb://localhost")
