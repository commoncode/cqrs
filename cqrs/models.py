from django.db import models
from polymorphic.polymorphic_model import PolymorphicModel
from django.utils.module_loading import import_by_path


class CQRSModel(models.Model):
    """A non-polymorphic CQRS model."""

    class Meta:
        abstract = True


class CQRSPolymorphicModel(CQRSModel, PolymorphicModel):
    """A polymorphic CQRS model."""

    @classmethod
    def _model_class_from_type_path(self, type_path):
        '''
        Get a model class from a type path as emitted by _type_path.

        This is used by the serializer.

        :raises: :exc:`django.core.exceptions.ImproperlyConfigured` or
                 :exc:`TypeError`, for illegal type paths.
        '''
        return import_by_path(type_path)

    @property
    def _type_path(self):
        '''
        Get the model's path. Used by the serializer.

        (We could use the ContentType, but that'd be rather inefficient and
        unnecessary; django-polymorphic has already done that for us by giving
        us an instance of the right type.)
        '''
        type_ = type(self)
        return '{}.{}'.format(type_.__module__, type_.__name__)

    class Meta:
        abstract = True
