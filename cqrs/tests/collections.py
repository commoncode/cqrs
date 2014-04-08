from ..collections import (DRFPolymorphicDocumentCollection,
                           DRFDocumentCollection, SubCollection)

from .models import (ModelA, ModelM, ModelAM, ModelAMM, ModelMAM, BoringModel,
                     OneMixingBowl, AnotherMixingBowl, AutomaticMixer)


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


class BoringCollection(DRFDocumentCollection):
    model = BoringModel


class OneMixingBowlCollection(DRFDocumentCollection):
    model = OneMixingBowl


class AnotherMixingBowlCollection(DRFDocumentCollection):
    model = AnotherMixingBowl


class AutomaticMixerCollection(DRFDocumentCollection):
    model = AutomaticMixer
