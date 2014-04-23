Models
======

There is nothing at all magic about the models part of CQRS.

Non-polymorphic models
----------------------

.. autoclass:: cqrs.models.CQRSModel

Using this is simple: just change the base class for your model from
:class:`django.db.models.Model` to :class:`cqrs.models.CQRSModel`.

:class:`~cqrs.models.CQRSModel` is a direct child of
:class:`django.db.models.Model` and adds absolutely nothing; its sole purpose
is to mark classes as CQRS-ready, for the benefit of the serializers.

Polymorphic models
------------------

.. autoclass:: cqrs.models.CQRSPolymorphicModel

You may also have polymorphic models; they work in much the same way, but use
the base class :class:`cqrs.models.CQRSPolymorphicModel` instead.

Because it uses django-polymorphic_, the default manager will return objects of
the most refined class.

:class:`~cqrs.models.CQRSPolymorphicModel` is a direct child of
:class:`django.db.models.Model` and adds absolutely nothing; its sole purpose
is to mark classes as CQRS-ready, for the benefit of the serializers.

.. _django-polymorphic: http://django-polymorphic.readthedocs.org/en/latest/
