import weakref

from denormalize.models import DocumentCollection

from .register import Register, RegisterableMeta
from .serializers import CQRSSerializerMeta
from .models import CQRSModel, CQRSPolymorphicModel


class DRFDocumentCollectionBaseMeta(type):
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

    def __init__(cls, *args, **kwargs):
        # If CQRSModel and CQRSPolymorphicModel are refactored so that the
        # latter does not inherit from the former, then the concept of
        # _required_not_model_base could be removed completely.

        # These bases are permitted to have no model, but everything else must
        # have a model.
        model_expected = cls.model is not None or cls.__name__ not in (
            'DRFDocumentCollectionBase', 'DRFDocumentCollection',
            'DRFPolymorphicDocumentCollection', 'SubCollection')

        if model_expected:
            if cls.model is None:
                raise TypeError("{!r} has no model specified"
                                .format(cls.__name__))
            if (getattr(cls, '_required_not_model_base', None) is not None
                    and issubclass(cls.model, cls._required_not_model_base)):
                raise TypeError(
                    'type {!r} uses model {!r} which is derived from {!r} '
                    '(not a permitted base)'.format(
                        cls.__name__, cls.model.__name__,
                        cls._required_not_model_base.__name__))

            if (getattr(cls, '_required_model_base', None) is not None
                    and not issubclass(cls.model, cls._required_model_base)):
                raise TypeError(
                    'type {!r} uses model {!r} which is not derived from {!r}'
                    .format(cls.__name__, cls.model.__name__,
                            cls._required_model_base.__name__))

        super(DRFDocumentCollectionBaseMeta, cls).__init__(*args, **kwargs)


class DRFDocumentCollectionBase(DocumentCollection):
    """
    A document collection making use of Django REST framework serializers for
    serializing our objects. This provides more power in what data we want to
    retrieve.

    This class is abstract.
    """
    __metaclass__ = DRFDocumentCollectionBaseMeta
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


class DRFDocumentCollectionMeta(DRFDocumentCollectionBaseMeta,
                                RegisterableMeta):
    """
    Metaclass for DRF document collections, taking care of registration.
    """

    # _register = DocumentCollectionRegister()
    # (defined at the end of the file as it's cyclic)

    @property
    def _model_for_registrar(cls):
        return getattr(cls, 'model', None)


class DRFDocumentCollection(DRFDocumentCollectionBase):
    """
    A non-polymorphic, Django REST framework-based document collection.

    Do not use this as the base for polymorphic models; use
    :class:`DRFPolymorphicDocumentCollection` instead.
    """

    __metaclass__ = DRFDocumentCollectionMeta
    _required_model_base = CQRSModel
    _required_not_model_base = CQRSPolymorphicModel

    def dump_obj(self, model, obj, path):
        """Use Django REST framework to serialize our object."""
        return self.serializer_class(obj).data


class DocumentCollectionRegister(Register):
    """
    A registry of document collections.

    Please, please remember with this that unlike the serializers, where
    everything is registered, with this only the *subcollections* are
    to be registered here. The root collections are *not* registered here; they
    get registered in a different way (and manually, at that) in the
    django-denormalize backend.
    """

    value_type = DRFDocumentCollection

    @staticmethod
    def is_valid_for(model_class, collection_class):
        return model_class is collection_class.model

    def create_value_for(self, model_class):
        class NewCollection(DRFDocumentCollection):
            model = model_class
            serializer_class = CQRSSerializerMeta._register[model_class]

        NewCollection.__name__ = '{}AutoDRFDocumentCollection'.format(
            model_class.__name__)
        # Changing __module__ might be a little dubious, but I'll do it anyway.
        NewCollection.__module__ = model_class.__module__
        NewCollection.__doc__ = (
            'Automatically generated DRF document collection for {}.'
            .format(model_class.__name__))
        return NewCollection


DRFDocumentCollectionMeta._register = DocumentCollectionRegister()


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

    def collection_or_subcollection_for(self, model_class):
        """
        Get this collection (``self``), or an instance of the appropriate
        subcollection, for the specified model class.
        """

        if self.serializer_class.Meta.model is model_class:
            return self
        else:
            subcollection = SubCollectionMeta._register.instances[model_class]
            subcollection.base_collection = weakref.proxy(self)
            return subcollection

    def dump_obj(self, model, obj, path):
        """Use Django REST framework to serialize our object."""

        collection = self.collection_or_subcollection_for(type(obj))
        if collection is self:
            return collection.serializer_class(obj).data
        else:
            return collection.dump_obj(model, obj, path)


class SubCollectionMeta(DRFDocumentCollectionMeta, RegisterableMeta):
    """
    Metaclass for subcollections, taking care of registration.
    """

    # _register = SubCollectionRegister()
    # (defined at the end of the file as it's cyclic)

    @property
    def _model_for_registrar(cls):
        return getattr(cls, 'model', None)


class SubCollection(DRFDocumentCollectionBase):
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

    __metaclass__ = SubCollectionMeta

    def __init__(self):
        if self.model is None:
            raise NotImplementedError('Document.model not set')
        # Super also has this, which we must explicitly remove::
        #
        #     if not self.name:
        #         self.name = self.model._meta.db_table
        #
        # This is also why we're not calling super.__init__().

    @property
    def name(self):
        """
        Get the name of the parent collection, if possible.

        A subcollection has no identity of its own; its items should go in the
        parent collection; hence the sharing of name. Note all the same that
        subcollections should *not* be registered in the django-denormalize
        backend (and can't, because of the perceived name collision).

        :raises NotImplementedError: if ``self.base_collection`` is not defined
        """
        # XXX: I'm not at all sure this will be called, as we won't be
        # registering the subcollections (and in fact we couldn't register the
        # subcollections, because django-denormalize would complain of a
        # duplicated collection name).

        # The subcollection is stored in the collection of its base model.
        # Remember that the base model does not get a subcollection, but rather
        # a collection, so we genuinely can't access the base collection from
        # here, because at present we are not registering non-sub collections.
        if hasattr(self, 'base_collection'):
            return self.base_collection.name

        # Yes, this can be fixed without too much difficulty by starting to
        # register collections and looking up self.model.__mro__ to find the
        # last concrete subclass of CQRSPolymorphicModel, which is the base
        # model, and fetching its registered collection. Or you could scan
        # ``DRFPolymorphicDocumentCollection.__subclasses__()``! But at
        # present, I don't *think* that the subcollection's name will be
        # needed, so I left this stub.
        raise NotImplementedError("This {!r} does not have a name as it "
                                  "doesn't know its base collection"
                                  .format(type(self).__name__))

    def dump_obj(self, model, obj, path):
        """Use Django REST framework to serialize our object."""
        return self.serializer_class(obj).data

    def collection_or_subcollection_for(self, model):
        # If non-polymorphic, I don't have a subcollection, do I?
        assert self.serializer_class.Meta.model is model
        return self

    _required_model_base = CQRSPolymorphicModel


class SubCollectionRegister(Register):
    """
    A registry of subcollections.

    Please, please remember with this that unlike the serializers, where
    everything is registered, with this only the *subcollections* are
    to be registered here. The root collections are *not* registered here; they
    get registered in a different way (and manually, at that) in the
    django-denormalize backend.
    """

    value_type = SubCollection

    @staticmethod
    def is_valid_for(model_class, subcollection_class):
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
