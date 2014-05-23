'''
CQRS serializer bases.

See :mod:`cqrs` docs for a full explanation.
'''

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_by_path
from rest_framework import serializers
from rest_framework.fields import CharField

from .models import CQRSModel, CQRSPolymorphicModel
from .register import Register, RegisterableMeta


def cqrs_base(model):
    """
    Get the appropriate concrete CQRS model base (there can be only one) for a
    CQRS model.

    If there is no *concrete* CQRS model base, then
    :class:`~cqrs.models.CQRSPolymorphicModel` or
    :class:`~cqrs.models.CQRSModel` will be returned, as appropriate.
    (They, you see, have the exception which permits them to have serializers
    of sorts.)

    If things don't work out (e.g. a non-CQRS model is given) you'll get an
    :exc:`AssertionError`.
    """

    # Why one? Well, inheritance from multiple concrete models is not sound,
    # and an abstract model class cannot have a serializer (it blows up in
    # ModelSerializer.get_default_fields, because pk_field becomes None) at
    # present.

    bases = [b for b in model.__bases__
             if issubclass(b, CQRSModel)
             and not b._meta.abstract and not b._meta.proxy]

    if len(bases) == 1:
        return bases[0]
    else:
        # There can't be more than one, so there must be none.
        assert len(bases) == 0
        # That means we must look at *anywhere* in the tree for CQRSModel or
        # CQRSPolymorphicModel. (We look anywhere rather than just one level as
        # an abstract child of CQRSModel or CQRSPolymorphicModel is a feasible
        # scenario.)
        if issubclass(model, CQRSPolymorphicModel):
            return CQRSPolymorphicModel
        else:
            assert issubclass(model, CQRSModel)
            return CQRSModel


class CQRSSerializerMeta(serializers.SerializerMetaclass, RegisterableMeta):
    """
    Metaclass for CQRS serializers, taking care of registration and field
    detection.
    """

    # _register = SerializerRegister(), defined at the end of the file (cyclic)

    @property
    def _model_for_registrar(self):
        return getattr(self.Meta, 'model', None)

    def __new__(cls, name, bases, attrs):
        # You know, I call quite a few things in this code evil and magic; if I
        # were asked to specify one as being the most evil and underhanded,
        # this would be it without a doubt. But this is essential to being able
        # to reasonably derive serializers automatically (how does one inherit
        # from something that's not actually written anywhere outside of a
        # definitely private implementation detail?).
        if 'CQRSPolymorphicSerializer' in globals() and \
                bases == (CQRSPolymorphicSerializer,):
            bases = cls._register[cqrs_base(attrs['Meta'].model)],
        return super(CQRSSerializerMeta, cls).__new__(cls, name, bases, attrs)

    def __init__(cls, *args, **kwargs):
        super(CQRSSerializerMeta, cls).__init__(*args, **kwargs)

        if 'CQRSPolymorphicSerializer' not in globals():
            # It's CQRSSerializer or CQRSPolymorphicSerializer
            return

        if cls.Meta.model._meta.proxy:
            # Yeah, I don't see any point in allowing this. It undermines
            # certain assumptions, whether it would work or not.
            raise AssertionError('CQRS serializer for proxy model? Verboten!')

        if cls.Meta.model._meta.abstract:
            # Not to say that we can't theoretically have serializers for them,
            # but for the present, it's no go, because for abstract classes
            # ModelSerializer.get_default_fields blows up because pk_field
            # becomes None. If we make it so that it *does* work, we'll
            # probably need to rethink some other things, especially to do with
            # CQRS mixins.

            raise AssertionError(
                'Cannot create serializer for abstract or proxy models.'
                ' (You tried to make serializer {!r} for {!r}.)'
                .format(cls.__name__, cls.Meta.model.__name__))


class SerializerRegister(Register):

    value_type = None  # defined below. Yeah, this is a really unpleasant
                       # three-way circular dependency :-(

    def is_valid_for(self, model, serializer):
        return ((model is serializer.Meta.model
            and not model._meta.abstract
            and not model._meta.proxy)
            # i.e. CQRSSerializer or CQRSPolymorphicSerializer
            or 'CQRSPolymorphicSerializer' not in globals())

    def create_value_for(self, model_class):
        if model_class is CQRSModel:
            base = CQRSSerializer
        elif model_class is CQRSPolymorphicModel:
            base = CQRSPolymorphicSerializer
        else:
            base = self[cqrs_base(model_class)]

        class NewSerializer(base):
            class Meta:
                model = model_class

        NewSerializer.__name__ = model_class.__name__ + 'AutoCQRSSerializer'
        # Changing __module__ might be a little dubious, but I'll do it anyway.
        NewSerializer.__module__ = model_class.__module__
        NewSerializer.__doc__ = (
            'Automatically generated CQRS serializer for {}.'
            .format(model_class.__name__))

        return NewSerializer


CQRSSerializerMeta._register = SerializerRegister()


class CQRSModelSerializerOptions(serializers.ModelSerializerOptions):
    def __init__(self, meta):
        super(CQRSModelSerializerOptions, self).__init__(meta)
        if self.fields:
            # If self.fields is not defined, then 'id' will automatically be
            # added; if we were to define it, then it would mean to *only* show
            # that field, which is certainly not what we want.
            self.fields = ('id',) + tuple(self.fields)

        # Polymorphic models must remove this field
        self.exclude = ('polymorphic_ctype',) + tuple(self.exclude)


class CQRSSerializer(serializers.ModelSerializer):

    __metaclass__ = CQRSSerializerMeta

    _options_class = CQRSModelSerializerOptions

    def get_default_fields(self):
        """
        Return the PARTIAL set of default fields for the object, as a dict.

        This differs from
        :meth:`rest_framework.serializers.ModelSerializer.get_default_fields`
        in that it only returns the *newly added fields*: that is, the fields
        from this class but not from one of its CQRS bases (thus, fields from
        non-CQRS mixins *are* included).

        ``get_fields`` will blend everything back together again. This is just
        so that ``fields`` can be defined in a sane fashion.
        """

        if type(self) in (CQRSSerializer, CQRSPolymorphicSerializer):
            # At present, these two are the only abstract model serializers
            # permitted; all others are forbidden outright, these are a
            # necessary evil (?). get_fields() and get_default_fields() fall
            # apart for abstract models, so we must return immediately here to
            # prevent such failure.
            return {}

        fields = super(CQRSSerializer, self).get_default_fields()

        # Now we go through all model bases' serializers and remove all their
        # fields. This will work recursively, of course, so it's all good.
        for base in type(self).__bases__:
            # Get a cached instance for it for performance
            # (Functionally, it'd be fine to write ``base = base()``)
            base = CQRSSerializerMeta._register.instances[base.Meta.model]
            # Note carefully that we use the get_default_fields() from super,
            # not our own one. This is so that we cut the fields from *all*
            # superclasses out, not just immediate superclasses. This permits
            # us to have three levels of inheritance.
            if type(base) in (CQRSSerializer, CQRSPolymorphicSerializer):
                # The super impl for these ones will fail, so skip it.
                continue
            for key in super(CQRSSerializer, base).get_default_fields():
                # All keys are guaranteed to exist. We'll keep id in for the
                # convenience of subclasses, so that we can add 'id' to
                # self.opts.fields and have it work.
                if key != 'id':
                    del fields[key]

        # There; we're down to just the ones defined by this model.
        return fields

    def get_fields(self):
        """
        Returns the complete set of fields for the object as a dict.

        This will be the set of any explicitly declared fields,
        plus the set of fields returned by get_default_fields().

        Significantly, however, this goes including the base serializers'
        fields once again.
        """

        fields = super(CQRSSerializer, self).get_fields()

        if type(self) is not CQRSSerializer:
            # (No more fields to add if it's CQRSSerializer.)

            # Much the same incantation as in get_default_fields, except this time
            # we're adding super's fields back in.
            # Do it in reverse order in order to maintain order. That's an order.
            for base in type(self).__bases__[::-1]:
                base = CQRSSerializerMeta._register.instances[base.Meta.model]
                new_fields = base.get_fields()
                # For these new fields, we're going to need to do this part
                # (from super.get_fields) again, so that we get the *right*
                # object ownership.
                for key, field in new_fields.items():
                    field.initialize(parent=self, field_name=key)
                new_fields.update(fields)
                fields = new_fields

        # Good! All is put back together again. Rejoice and be exceeding glad.
        return fields

    class Meta:
        # Here and on all subclasses, ``fields``, ``exclude``,
        # ``write_only_fields``, et al. *only apply to newly added fields*
        # (fields defined directly in ``model`` or any non-CQRS bases)
        model = CQRSModel


SerializerRegister.value_type = CQRSSerializer


class CQRSPolymorphicSerializer(CQRSSerializer):
    '''
    Serializer for Polymorphic Model
    '''

    type = CharField(source='_type_path', read_only=True)

    class Meta:
        model = CQRSPolymorphicModel

    def to_native(self, obj):
        '''
        Because OfferAspect is Polymorphic and don't know ahead of time
        which downcast model we'll be dealing with
        '''

        if CQRSSerializerMeta._register[type(obj)] == type(self):
            # We have the correct serializer class.
            # Rejoice and be exceeding glad.
            return super(CQRSPolymorphicSerializer, self).to_native(obj)
        # Otherwise, do this quick dodge where we effectively substitute self
        # for a different (more precise) serializer
        return CQRSSerializerMeta._register.instances[type(obj)].to_native(obj)

    def from_native(self, data, files=None, polymorphism_resolved=False):
        """
        Deserialize primitives -> polymorphic objects.
        """

        if polymorphism_resolved:
            # We've got the right serializer, so now we can continue normally.
            return super(CQRSPolymorphicSerializer, self).from_native(data,
                                                                      files)

        # The ``type`` field is a magic one, because we need it to determine
        # which *serializer* to use. It obviously can't be done with a regular
        # field, and so it is marked read only and handled inside this method.

        self._errors = {}

        # If we can, retrieve the 'type' field, which is a model path.
        if 'type' not in data:
            self._errors['type'] = ['No polymorphic type provided.']
            return

        try:
            model_class = import_by_path(data['type'])
            # Now get the correct serializer for that model class.
            serializer = CQRSSerializerMeta._register.instances[model_class]
        except (ImproperlyConfigured, TypeError):
            self._errors['type'] = ['Invalid type {!r}.'.format(data['type'])]
            return

        # It's OK to leave 'type' in; it'll just sit there unused.

        # Now we can defer to that serializer's from_native. And tell ourselves
        # that the polymorphism is resolved to make sure we don't recurse.
        return serializer.from_native(data=data, files=files,
                                      polymorphism_resolved=True)
