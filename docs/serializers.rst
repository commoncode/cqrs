Serializers
===========

CQRS uses `Django REST framework`_ serializers.

Unlike the :doc:`models <models>`, there is some magic in the serializers.
Here's how it all works.

.. _Django REST framework: http://www.django-rest-framework.org/

.. .. autoclass:: cqrs.serializers.CQRSSerializer

.. .. autoclass:: cqrs.serializers.CQRSPolymorphicSerializer

Automatically derived serializers
---------------------------------

If no serializer is specified for a model class, one is automatically
derived when necessary, thus (given a model ``Foo``)::

    class FooAutoCQRSSerializer(base CQRS serializer):
       class Meta:
           model = Foo

That's it. No inheritance for ``Meta`` (if you want that, you'll need to
specify it yourself), no ``Meta.fields``, nothing particularly fancy. The fancy
stuff occurs later.

The only part that requires any explanation is the part  marked "base CQRS
serializer"; this equates to the serializer of the model class's CQRS base,
with ``CQRSSerializer`` considered to be ``CQRSModel``'s serializer and
``CQRSPolymorphicSerializer`` ``CQRSPolymorphicModel``'s. Giving a few
examples:

- For ``class Foo(CQRSModel)``,
  ``class FooAutoCQRSSerializer(CQRSSerializer)``.

- For ``class Foo(CQRSPolymorphicModel)``,
  ``class FooAutoCQRSSerializer(CQRSPolymorphicSerializer)``.

- For ``class Foo(Bar, SomeMixin)`` (``Bar`` being a CQRS model, polymorphic or
  non-polymorphic, it doesn't matter, and ``SomeMixin`` being an abstract
  model, CQRS or otherwise), ``class FooAutoCQRSSerializer(BarSerializer)``,
  where ``BarSerializer`` might be a manually specified serializer or an
  automatically derived serializer.

Observe that there will always be exactly one base CQRS serializer, for only
concrete models, ``CQRSModel`` and ``CQRSPolymorphicModel`` can have
serializers. (If you try to create a serializer for an abstract or proxy model
you will get an :exc:`AssertionError`. Also, incidentally, if you get the bases
wrong, you will get an :exc:`AssertionError`.)

Earlier I said that a serializer would be derived "when necessary"; there are
two cases when this may happen:

1. When a serializer is defined for a model's subclass (in order to sort out
   its bases)

2. For children of polymorphic models, when one uses the root polymorphic
   model's serializer to dump an instance of that child class.

Basically, it's just "when you use it".

.. admonition:: Caution

   Be careful to ensure that your serializers are imported before you get to
   using them, or they won't be—serializers will be derived automatically
   instead. To prevent this from being a problem, a ``serializers`` module is
   imported from all ``INSTALLED_APPS`` that have it (in much the same way as
   ``models.py``). This indicates the recommended place for CQRS serializers.

A little bit of magic: the :class:`~cqrs.serializers.CQRSPolymorphicSerializer` base
------------------------------------------------------------------------------------

There is only one special thing that happens at class construction time: if
your class has the single base class
:class:`~cqrs.serializers.CQRSPolymorphicSerializer`, then the appropriate base
is found (the serializer's model's CQRS base's serializer) and substituted in
``CQRSPolymorphicSerializer``'s place.

This is moderately evil, but allows you to omit an intermediate serializer
which can be automatically derived (by the rules in the previous section), for
the automatically derived serializer will now be used in its stead.

Fields included in serialization
--------------------------------

This is the main part of significant interest. We try to do things the Django
REST framework way, but not everything can be done that way. The precise
behaviour of working out the fields that will be serialized is the best example
of this, for Django REST framework does not have especially good support for
polymorphic serializers.

The change in behaviour in CQRS serializers is this:

**Each serializer applies only to the new fields in the serializer.**

"New fields" is defined as any model fields that come not from a concrete
model. That is, fields defined explicitly in the model itself or which come
from a mixin.

Each serializer, when calculating its fields, operates upon this set, and then
adds to it its base class's fields, calculated recursively in like manner.
Thus, all fields are accounted for, with convenient exclusion of fields or
manual definition of fields to show, only needing to deal with the fields that
you defined, and not those of superclasses or subclasses.

Beyond that, all works as you would expect from Django REST framework: by
default all fields are included, including manually specified serializer
fields; if you specify ``Meta.fields``, it will filter that set down to the
named fields; if you specify ``Meta.exclude``, fields named therein will be
removed. Because each serializer only applies to new fields, you very
deliberately cannot remove fields from a base class. (This is sound Object
Orientation according to the Open-Closed Principle.)

(This is all implemented by overriding the behaviour of the ``get_fields`` and
``get_default_fields`` methods.)

The 'id' field
--------------

All models MUST use the ``id`` field as their primary key. This field is
included in all serializers and may not be excluded.

Polymorphic serializers
-----------------------

For polymorphic serializers, the precise type is encoded in a field named
``type``; this is filled with the path to the class, e.g.
``"myapp.models.MyModel"``.

.. admonition:: Implementer's note on that "``type``" field

   Want to change how the type is serialized on a per-serializer basis? It
   won't be as easy as you might like. At present, we have ``_type_path`` and
   ``_model_class_from_type_path`` on
   :class:`~cqrs.models.CQRSPolymorphicModel`; this is because of Django REST
   framework's design:

      Extra fields can correspond to any property or callable on the model.

   — `Django REST framework documentation, Serializers, Specifying fields
   explicitly
   <http://www.django-rest-framework.org/api-guide/serializers#specifying-fields-explicitly>`_

   This will need to be worked around so that they can be on the serializer
   instead.
