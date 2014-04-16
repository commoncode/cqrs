from django.db import models
from polymorphic.polymorphic_model import PolymorphicModel


class CQRSModel(models.Model):
    """A non-polymorphic CQRS model."""

    class Meta:
        abstract = True


class CQRSPolymorphicModel(CQRSModel, PolymorphicModel):
    """A polymorphic CQRS model."""

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
