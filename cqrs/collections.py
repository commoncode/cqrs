from django.utils.module_loading import import_by_path
from django.utils import six

from denormalize.models import DocumentCollection

from .register import Register, RegisterableMeta
from .serializers import CQRSSerializerMeta
from .models import CQRSModel, CQRSPolymorphicModel


class DRFDocumentCollectionMeta(type):
    '''
    A document collection metaclass, enforcing appropriate model subclassing.

    The goal of this metaclass is to make it much harder for people to make
    mistakes which would lead to *parts* of the system working, but not other
    parts. e.g. using a polymorphic model on a non-polymorphic collection would
    leave get_related_models broken, which might not be noticed for ages,
    because dump_obj will normally work without needing to use the polymorphic
    collection (owing the the serializer automatically switching to the correct
    serializer). But if the collection is overridden, it won't.

    So we save that trouble by allowing a
    :class:`DRFPolymorphicDocumentCollection` subclass to require a
    :class:`cqrs.models.CQRSPolymorphicModel` subclass, on pain of
    :exc:`TypeError`, and the same for non-polymorphic collections.
    '''

    def __init__(self, *args, **kwargs):
        # If CQRSModel and CQRSPolymorphicModel are refactored so that the
        # latter does not inherit from the former, then the concept of
        # _required_not_model_base could be removed completely.

        # These bases are permitted to have no model, but everything else must
        # have a model.
        model_expected = self.model is not None or self.__name__ not in (
            'DRFDocumentCollectionBase', 'DRFDocumentCollection',
            'DRFPolymorphicDocumentCollection', 'SubCollection', 'NewBase')

        if model_expected:
            if self.model is None:
                raise TypeError("{!r} has no model specified"
                    .format(self.__name__))
            if (getattr(self, '_required_not_model_base', None) is not None
                and issubclass(self.model, self._required_not_model_base)):
                raise TypeError(
                    'type {!r} uses model {!r} which is derived from {!r} '
                    '(not a permitted base)'.format(
                        self.__name__, self.model.__name__,
                        self._required_not_model_base.__name__))

            if (getattr(self, '_required_model_base', None) is not None
                and not issubclass(self.model, self._required_model_base)):
                raise TypeError(
                    'type {!r} uses model {!r} which is not derived from {!r}'
                    .format(self.__name__, self.model.__name__,
                            self._required_model_base.__name__))

        super(DRFDocumentCollectionMeta, self).__init__(*args, **kwargs)


class DRFDocumentCollectionBase(six.with_metaclass(DRFDocumentCollectionMeta,
                                                   DocumentCollection)):
    """
    A document collection making use of Django REST framework serializers for
    serializing our objects. This provides more power in what data we want to
    retrieve.

    This class is abstract.
    """
    _required_model_base = None
    _required_not_model_base = None

    # TODO: How to deal with stale foreign key data being cached in mongo?

    # A note on what needs to be overridden: pretty much only dump_obj and
    # get_related_models. As examples of others: dump is OK (it does check
    # isinstance(root_obj, self.model), but subclasses are good).
    # dump_collection is based upon queryset() which uses the default manager,
    # which is a polymorphic manager, so that works too. It's pleasant how most
    # of the potential problems you might have actually aren't problems :-)

    # TODO: consider whether we should override get_related_models in such a
    # way that it uses the serializer rather than the model, or if this even
    # makes sense. (Dunno.)

    @property
    def serializer_class(self):
        return CQRSSerializerMeta._register[self.model]

    def concreteify_serializer_class(self):
        """Eww, bad name. Resolve self.serializer_class if necessary."""
        if isinstance(self.serializer_class, str):
            self.serializer_class = import_by_path(self.serializer_class)

    # Parent DRFDocumentCollection (for saving child objects).
    # TODO(Chris): nuke this and in mongo, for never in all git history was it
    # set.
    parent_collection = None


class DRFDocumentCollection(DRFDocumentCollectionBase):
    """
    A non-polymorphic, Django REST framework-based document collection.

    Do not use this as the base for polymorphic models; use
    :class:`DRFPolymorphicDocumentCollection` instead.
    """

    _required_model_base = CQRSModel
    _required_not_model_base = CQRSPolymorphicModel

    def dump_obj(self, model, obj, path):
        """Use Django REST framework to serialize our object."""
        self.concreteify_serializer_class()
        return self.serializer_class(obj).data


class DRFPolymorphicDocumentCollection(DRFDocumentCollectionBase):
    """
    A polymorphic, Django REST framework-based document collection.

    Each root polymorphic class (i.e. each immediate, non-abstract descendant
    of :class:`~cqrs.models.CQRSPolymorphicModel`) needs to have a subclass of
    this class. Then its subclasses can have :class:`SubCollection` subclasses,
    or (more commonly) use an automatically implemented subcollection.

    Do not use this as the base for non-polymorphic models; use
    :class:`DRFDocumentCollection` instead.
    """

    _required_model_base = CQRSPolymorphicModel

    def get_related_models(self):
        """
        A replacement get_related_models method, coping with polymorphic models
        by using the subcollections concept.

        The long term idea is that it should take its hints from the CQRS
        serializer rather than the model, but that's not happening at present.

        This is to "determine on which models the return data might depend, and
        the query to determine the affected objects" (quote from
        ``DocumentCollection.get_related_models.__doc__``, see it for more
        information).
        """
        model_info = super(DRFPolymorphicDocumentCollection,
            self).get_related_models()
        for cls in self.model.__subclasses__():
            if cls._meta.abstract or cls._meta.proxy:
                # We have no interest in abstract classes: the fields are
                # included in their children and they are not concrete. Proxy
                # classes are also of no interest as they are nothing to do
                # with the database.
                continue
            subcollection = SubCollectionMeta._register.instances[cls]
            # This may or may not be sound. I really don't know. I haven't
            # thought about it much or looked at how get_related_models is
            # used. This might be completely unsound. I guess we'll see soon
            # enough. -- Chris
            model_info.update(subcollection.get_related_models())
        return model_info

    def dump_obj(self, model, obj, path):
        """Use Django REST framework to serialize our object."""
        self.concreteify_serializer_class()

        if self.serializer_class.Meta.model is self.model:
            # One of two situations:
            # (a) This is the root collection (probably not a SubCollection
            #     subclass either, so we'd better not do the lookup!), or
            # (b) lookup has already been done and this is a subcollection.
            return self.serializer_class(obj).data

        subcollection = SubCollectionMeta._register.instances[type(obj)]
        return subcollection.dump_obj(model, obj, path)


class SubCollectionMeta(DRFDocumentCollectionMeta, RegisterableMeta):
    """
    Metaclass for subcollections, taking care of registration.
    """

    # _register = SubCollectionRegister()
    # (defined at the end of the file as it's cyclic)

    @property
    def _model_for_registrar(self):
        return getattr(self, 'model', None)


class SubCollection(six.with_metaclass(SubCollectionMeta,
                                       DRFDocumentCollection)):
    """
    A partial, non-polymorphic document collection for children of polymorphic
    models; each child of a polymorphic model can have one of these, or one
    will be automatically generated. This allows you to override the
    collection's behaviour for a specific class.

    Some of the perks of ``DocumentCollection``, things like ``select_related``
    and ``prefetch_related``, might not work properly at present; they're added
    to the polymorphic collection, but may not work correctly. We haven't tried
    them at all. So be careful.
    """

    _required_model_base = CQRSPolymorphicModel
    _required_not_model_base = None


class SubCollectionRegister(Register):

    value_type = SubCollection

    def is_valid_for(self, model_class, subcollection_class):
        return model_class is subcollection_class.model

    def create_value_for(self, model_class):
        # Whew, after all that serializer stuff, this one is *delightfully*
        # easy: the only thing to take care of in creating the class is the
        # inheritance!
        bases = tuple(self[cls] for cls in model_class.__bases__
                      if issubclass(cls, CQRSPolymorphicModel))
        # TODO: consider shifting the base shifting into the metaclass
        return SubCollectionMeta(
            model_class.__name__ + 'AutoSubCollection',
            bases + (SubCollection,),
            {'model': model_class,
             '__module__': model_class.__module__,
             '__doc__': 'Automatically generated subcollection for {}.'
                        .format(model_class.__name__)})


SubCollectionMeta._register = SubCollectionRegister()
