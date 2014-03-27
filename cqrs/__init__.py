# coding: utf-8
u"""
CQRS for Django + Django REST Framework + django-polymorphic +
django-denormalize + MongoDB.

(CQRS stands for Command Query Responsibility Segregation.)

Here's an explanation of what this is all about.

The normal models and serizializers
===================================

To take advantage of CQRS functionality, your models should extend
:class:`~cqrs.models.CQRSModel` and your serializers
:class:`~cqrs.serializers.CQRSSerializer`.

:class:`~cqrs.models.CQRSModel` adds a ``mongoID`` field, which
:class:`~cqrs.serializers.CQRSSerializer` also includes.

If you have a polymorphic model, you should use
:class:`~cqrs.models.CQRSPolymorphicModel` and
:class:`~cqrs.serializers.CQRSPolymorphicSerializer` for your model and
serializer bases, respectively. The former takes care of its being a
django-polymorphic ``PolymorphicModel`` and the latter takes care of creating
and sustaining polymorphic serializers, which we're just about to talk about.

CQRS polymorphic serializers
============================

The basic concept here is having a Django REST Framework serializer which can
automatically serialize a polymorphic model (i.e. a model with subclasses)
without needing to specify new serializers for added fields. It does this while
supporting manually specified serializers as well, including even multiple
inheritance.

This does come with tradeoffs; there can only be one CQRS serializer per model
class, creating a coupling between the model and serializer that is contrary to
the spirit of DRF. If you go specifying a serializers for one of your models,
you must ensure that it is imported before you try using it, or else an
automatic serializer will be created instead, and if you then try to use your
own, things will break.

It is also important to note that ``to_native`` is the only method of
:class:`~cqrs.serializers.CQRSPolymorphicSerializer` which is designed to use
the appropriate serializer; other parts will not at present do so.

For an example of usage, take a look at :mod:`cqrs.tests`.

It's time for some ASCII art. Well, Unicode art seeing as I didn't use ``+``,
``-`` and ``|`` but instead the appropriate Unicode box drawing characters.

::

    ┌──────────────────────┐
    │ CQRSPolymorphicModel │
    ├──────────────────────┤
    │ id                   │
    │ mongoID              │
    └──────────────────────┘
               ^
               |
          ┌─────────┐
          │ Product │
          ├─────────┤
          │ price   │
          │ secret  │
          └─────────┘
            ^     ^
            |     |
    ┌────────┐   ┌──────────┐
    │ Book   │   │ URL      │
    ├────────┤   ├──────────┤
    │ isbn   │   │ url      │
    └────────┘   │ password │
           ^     └──────────┘
           |       ^
           |       |
         ┌───────────┐
         │ EBook     │
         ├───────────┤
         │ version   │
         └───────────┘

There, now we have a delightfully complex model with the diamond inheritance
cherry on top.

Let us assume that in the CQRS serialized form of a URL (and thus an eBook) you
doesn't want to serialize the password, but rather a hash of it. Yeah, that
might be a little contrived, but it suits just at present. You also don't want
to include a product's secret.

Expressed in code, the models come out like this::

    class Product(CQRSPolymorphicModel):
        price = …
        secret = …


    class Book(Product):
        isbn = …


    class URL(Product):
        url = …
        password = …

        def password_hash(self):
            …

    class EBook(Book, URL):
        version = …

Now we get to the fun matter of making serializers for these. Here's what we
might write::

    class ProductSerializer(CQRSPolymorphicSerializer):
        class Meta:
            fields = 'price',


    class URLSerializer(CQRSPolymorphicSerializer):
        password_hash = CharField(read_only=True)

        class Meta:
            fields = 'url',

(While it might be considered better to write ``ProductSerializer`` with
``exclude = 'secret',`` instead of ``fields = 'price',``, ``exclude`` is not
supported at the time of writing due to slight complications it would introduce
with multiple inheritance. It's not insurmountable, but it was easier to
ignore. It will raise a :exc:`NotImplementedError` if you try to use it, so
you're still safe.)

When you come to use it, given a variable ``product`` which might be a
``Product`` or a ``Book`` or a ``URL``, you can use
``ProductSerializer().to_native(product)`` if you desire, or you can use
``CQRSPolymorphicSerializer().to_native(product)``—they will have the same
effect.

There are a few magic things to note here. First of all I'll draw a diagram of
the serializer inheritance that actually takes place. The fields in the diagram
are the entries *added* in Meta.fields*; each class has the items of its
parents' Meta.fields added to it::

                  ┌───────────────────────────┐
                  │ CQRSPolymorphicSerializer │
                  ├───────────────────────────┤
                  │ id                        │
                  │ mongoID                   │
                  └───────────────────────────┘
                               ^
                               |
                      ┌───────────────────┐
                      │ ProductSerializer │
                      ├───────────────────┤
                      │ price             │
                      └───────────────────┘
                          ^        ^
                          |        |
    ┌────────────────────────┐   ┌───────────────┐
    │ BookAutoCQRSSerializer │   │ URLSerializer │
    ├────────────────────────┤   ├───────────────┤
    │ isbn                   │   │ url           │
    └────────────────────────┘   │ password_hash │
                          ^      └───────────────┘
                          |        ^
                          |        |
                      ┌─────────────────────────┐
                      │ EBookAutoCQRSSerializer │
                      ├─────────────────────────┤
                      │ version                 │
                      └─────────────────────────┘

Expressed in code, it is approximately::

    class ProductSerializer(CQRSPolymorphicSerializer):
        class Meta:
            fields = 'id', 'mongoID', 'price'


    class BookAutoCQRSSerializer(ProductSerializer):
        class Meta:
            fields = 'id', 'mongoID', 'price', 'isbn'


    class URLSerializer(ProductSerializer):
        class Meta:
            fields = 'id', 'mongoID', 'price', 'url'


    class BookAutoCQRSSerializer(ProductSerializer):
        class Meta:
            fields = 'id', 'mongoID', 'price', 'isbn'


    class EBookAutoCQRSSerializer(BookAutoCQRSSerializer, URLSerializer):
        class Meta:
            fields = 'id', 'mongoID', 'price', 'isbn', 'url'

Now on to the things to note:

1. ``Book`` has a serializer created for it, which is named
   ``BookAutoCQRSSerializer``. Ditto for ``EBook``. In each case, the
   inheritance is modelled so as to match that of the model classes.

2. ``URLSerializer``'s bases are *changed* from
   ``(CQRSPolymorphicSerializer,)`` to ``(ProductSerializer,)`` (note also how
   ``EBookAutoCQRSSerializer`` has matching inheritance; had it been manually
   specified with :class:`~cqrs.serializers.CQRSPolymorphicSerializer` as its
   only base, it would also have had its bases changed).

   This is only done if :class:`~cqrs.serializers.CQRSPolymorphicSerializer` is
   the only base, or when a serializer is automatically derived. So remember to
   be careful.

3. Manually specified fields are automatically added to ``Meta.fields``.

4. ``Meta.fields`` is updated in all classes so that the data exposed in a
   subclass is a superset of that of its superclass. (This is sound OO theory,
   even if it's something that Django REST Framework doesn't do for
   :class:`~rest_framework.serializers.ModelSerializer`.)
"""
