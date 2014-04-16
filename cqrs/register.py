"""
Utilities for keeping a registry of other classes that correspond to model
classes with a one-to-one correspondence.

This is used to keep track of things like which serializers belong to which
model classes.

There is the assumption that if a type does not exist, a default implementation
can be created.
"""

import weakref

from django.core.exceptions import ImproperlyConfigured

from .models import CQRSModel


class InstanceRegister(object):
    """
    A lazy dictionary-like register, indexed by model type and giving (shared,
    one per type) [value type] instances.
    """

    def __init__(self, type_register):
        self._type_register = weakref.proxy(type_register)
        self._instances = {}

    def __getitem__(self, type_):
        if type_ not in self._instances:
            self._instances[type_] = self._type_register[type_]()
        return self._instances[type_]


class Register(object):
    """
    A register of CQRS models and their related [value] types. Lazy and
    dictionary-like, indexed by model type and giving [value] classes.

    ([value] might be serializers, document subcollections, &c.)

    When you need instances, don't use ``self[model_class]()``; go for a little
    more efficiency by sharing instances: ``self.instances[model_class]``.

    See `SerializerRegister` for an example of the configuration that must be
    done.
    """

    def __init__(self):
        self._register = {}
        self.instances = InstanceRegister(self)
        if not hasattr(self, 'value_type'):
            raise ImproperlyConfigured('value_type not set')
        if not hasattr(self, 'is_valid_for'):
            raise ImproperlyConfigured('is_valid_for not defined')
        if not hasattr(self, 'create_value_for'):
            raise ImproperlyConfigured('create_value_for not defined')

    def __iter__(self):
        return iter(self._register)

    def __setitem__(self, model, value):
        if not self.is_valid_for(model, value):
            raise ValueError("{} is not a {} for {}"
                             .format(value, self.value_type.__name__, model))

        if CQRSModel not in model.__mro__:
            # We're too good for duck typing here.
            raise TypeError("Can't register {}.{}: its model {}.{} is not CQRS"
                            .format(value.__module__, value.__name__,
                                    model.__module__, model.__name__))
        if model in self._register:
            raise ImproperlyConfigured(
                "There is already a {} for {}"
                .format(self.value_type.__name__, model))
        self._register[model] = value

    def __getitem__(self, model):
        if CQRSModel not in model.__mro__:
            # We're too good for duck typing here.
            raise TypeError("Model {}.{} is not CQRS, can't be in register"
                            .format(model.__module__, model.__name__))
        if model not in self._register:
            self._register[model] = self.create_value_for(model)
        return self._register[model]


class RegisterableMeta(type):
    """
    Metaclass for registerable objects (the value types in a register), taking
    care of registration.

    Subclasses of this metaclass must define `_register` (an instance of a
    `Register` subclass) and a property `_model_for_registrar` (the model class
    that the type corresponds to).

    See `SerializerRegisterMeta` for an example of the configuration that must
    be done.
    """
    def __init__(cls, *args, **kwargs):
        super(RegisterableMeta, cls).__init__(*args, **kwargs)

        # TODO: we probably need to check fields at this point.
        # TODO: what about subclasses of the serializer?
        model = cls._model_for_registrar
        if model is not None:
            type(cls)._register[model] = cls
