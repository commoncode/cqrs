The concepts
============

**CQRS** stands for **Command/Query Responsibility Segregation**.

Distilled beyond recognition (look elsewhere to find descriptions of what CQRS
is supposed to be), this means that you write to one place and read from
another place, probably with the data in a different shape that you can work
with more effectively.

django-denormalize lets you do part of that, but only part. It has problems
with polymorphic classes and doesn't allow you to bend the data into different
shapes at all easily.

The solution: fix up the polymorphic stuff and use Django REST framework
serializers for the collections.

This package
============

This package allows you to easily maintain such a scheme in Django. It achieves
this by tying together Django_, django-polymorphic_, django-denormalize_ and
`Django REST framework`_.

It takes django-denormalize and replaces its own collection logic with Django
REST framework serializers.

It provides automatic derivation of serializers and good support for
polymorphism, thus tying Django REST framework in with django-polymorphic.

It also ties django-polymorphic and django-denormalize together with 
:class:`cqrs.backend.PolymorphicBackendBase`; you must ensure that the backend
that you use extends :class:`~cqrs.backend.PolymorphicBackendBase` to get
signals working appropriately on polymorphic models.

Also in :mod:`cqrs.mongo` there is a django-denormalize backend for MongoDB
which uses the ``id`` field as ``_id`` in the MongoDB collection.

.. _Django: http://djangoproject.com/
.. _django-polymorphic: http://django-polymorphic.readthedocs.org/en/latest/
.. _django-denormalize: https://bitbucket.org/wojas/django-denormalize/
.. _Django REST framework: http://www.django-rest-framework.org/
