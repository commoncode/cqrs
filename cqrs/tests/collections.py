from ..collections import DRFPolymorphicDocumentCollection, SubCollection

from .models import ModelA, ModelM, ModelAM, ModelAMM, ModelMAM


class ACollection(DRFPolymorphicDocumentCollection):
    # Yeah, I know A was for automatic. But this one can't be automatic (it's
    # the collection, only subcollections can be done automatically).
    model = ModelA


class MCollection(DRFPolymorphicDocumentCollection):
    model = ModelM


# Good morning (again).
class AMSubCollection(SubCollection):
    model = ModelAM


class AMMSubCollection(SubCollection):
    model = ModelAMM


class MAMSubCollection(SubCollection):
    model = ModelMAM
