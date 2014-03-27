from .mongo import CQRSModelMixin
from polymorphic.polymorphic_model import PolymorphicModel


class CQRSModel(CQRSModelMixin):

    class Meta:
        abstract = True


class CQRSPolymorphicModel(CQRSModelMixin, PolymorphicModel):

    class Meta:
        abstract = True
