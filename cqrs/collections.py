from django.utils.module_loading import import_by_path
from django.utils import six

from denormalize.models import DocumentCollection

from .register import Register, RegisterableMeta
from .serializers import CQRSSerializerMeta
from .models import CQRSPolymorphicModel


class DRFDocumentCollection(DocumentCollection):
    """
    Overrides `DocumentCollection` to make use of the Django Rest Framework
    serializer for serializing our objects. This provides more power in
    what data we want to retrieve.

    TODO: How to deal with stale foreign key data being cached in mongo?
    """

    @property
    def serializer_class(self):
        return CQRSSerializerMeta._register[self.model]

    # Parent DRFDocumentCollection (for saving child objects)
    parent_collection = None

    def __init__(self):
        super(DRFDocumentCollection, self).__init__()

    def get_related_models(self):
        """
        Override the get_related_models to disable the function. This will
        be done with Django Rest Framework instead
        """
        """
        A replacement get_related_models method, taking its hints primarily
        from the CQRS serializers instead of from models.

        This is to "determine on which models the return data might depend, and
        the query to determine the affected objects" (quote from
        DocumentCollection.get_related_models.__doc__).

        @@@ TODO: move this example to the class doc string

        Consider the following situation::

         * Our root collection is based on the model `Book`
         * The model `Chapter` has a `book` field pointing to a `Book`
         * The `Book` has a `publisher` field pointing to a `Publisher`
         * There is an `Author` model with a many-to-many relationship with
           `Book` through `Book.authors`

        The document declaration will contain the following::

            select_related = ['publisher']
            prefetch_related = ['chapter_set', 'authors']

        When a Chapter is added or updated, the affected book collections
        can be found using the following query::

            affected_books_1 = Book.objects.filter(publisher=publisher)
            affected_books_2 = Book.objects.filter(chapter_set=chapter)
            affected_books_3 = Book.objects.filter(authors=author)

        This also works over a '__' separated path. The nice thing here is
        that we do not need to perform extra work to determine the query
        filters.

        The return value for the book collection would be::

            {
                'chapter':   {'direct': False,
                              'm2m': False,
                              'model': <class 'Chapter'>,
                              'path': 'chapter_set'
                },
                'publisher': {'direct': True,
                              'm2m': False,
                              'model': <class 'Publisher'>,
                              'path': 'publisher__links'
                },
                'authors': {  'direct': True,
                              'model': <class 'Author'>,
                              'path': 'authors',
                              'through': <class 'Book_authors'>
                }
            }

        """
        self.concreteify_serializer_class()
        for cls in self.serializer_class.__subclasses__():
            if cls._meta.abstract or cls._meta.proxy:
                # We have no interest in abstract classes: the fields are
                # included in their children and they are not concrete. Proxy
                # classes are also of no interest as they are nothing to do
                # with the database.
                continue
            #TODO continue here: return get_related_models for cls
        return {}

    def concreteify_serializer_class(self):
        """Eww, bad name. Resolve self.serializer_class if necessary."""
        if isinstance(self.serializer_class, str):
            self.serializer_class = import_by_path(self.serializer_class)

    def dump_obj(self, model, obj, path):
        """
        Use Django Rest Framework to serialize our object
        """
        self.concreteify_serializer_class()

        if self.serializer_class.Meta.model is self.model:
            # One of two situations:
            # (a) This is the root collection (probably not a SubCollection
            #     subclass either, so we'd better not do the lookup!), or
            # (b) lookup has already been done and this is a subcollection.
            return self.serializer_class(obj).data

        # TODO: determine if we need to do anything else to the subclass to
        # make it play correctly (e.g. do we need to override .name?)
        sub_collection = SubCollectionMeta._register[type(obj)]()
        return sub_collection.dump_obj(model, obj, path)


class SubCollectionMeta(RegisterableMeta):
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
    A partial document collection, for polymorphic models; each child of a
    polymorphic model can have one of these, or one will be automatically
    generated. This allows you to override the collection's behaviour for a
    specific class.
    """


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
