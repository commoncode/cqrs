'''
CQRS serializer bases.

See :mod:`cqrs` docs for a full explanation.
'''

import weakref

from django.core.exceptions import ImproperlyConfigured
from django.utils import six
from rest_framework import serializers
from rest_framework.fields import Field, CharField

from .mongo import CQRSModelMixin
from .models import CQRSModel, CQRSPolymorphicModel


class SerializerInstanceRegister(object):
    """
    A lazy dictionary-like register, indexed by model type and giving (shared)
    serializer instances.
    """

    def __init__(self, type_register):
        self._type_register = weakref.proxy(type_register)
        self._instances = {}

    def __getitem__(self, type_):
        if type_ not in self._instances:
            self._instances[type_] = self._type_register[type_]()
        return self._instances[type_]


class SerializerRegister(object):
    """
    A register of CQRS models and their serializers. Lazy and dictionary-like,
    indexed by model type and giving serializer classes.

    When you need instances, don't use ``self[model_class]()``; go for a little
    more efficiency by sharing instances: ``self.instances[model_class]``.
    """

    def __init__(self):
        self._register = {}
        self.instances = SerializerInstanceRegister(self)

    def __iter__(self):
        return iter(self._register)

    def __setitem__(self, model, serializer):
        if model != serializer.Meta.model:
            raise ValueError("{} is not a serializer for {}"
                             .format(serializer, model))
        if CQRSModelMixin not in model.__mro__:
            # We're too good for duck typing here.
            raise TypeError("Can't register {}.{}: its model {}.{} is not CQRS"
                            .format(serializer.__module__, serializer.__name__,
                                    model.__module__, model.__name__))
        if model in self._register:
            raise ImproperlyConfigured(
                "There is already a CQRSSerializer for {}"
                .format(serializer.Meta.model))
        self._register[serializer.Meta.model] = serializer

    def __getitem__(self, model):
        if CQRSModelMixin not in model.__mro__:
            # We're too good for duck typing here.
            raise TypeError("Model {}.{} is not CQRS, can't be in register"
                            .format(model.__module__, model.__name__))
        if model not in self._register:
            self._register[model] = self.create_serializer_for(model)
        return self._register[model]

    def create_serializer_for(self, model_class):
        # Here we have the fun of constructing a serializer for a subclass.
        # Here are the things we need to do:
        #
        # - The serializer inheritance hierarchy should model that of the model
        #   class. But we only care about CQRS models; the others can be folded
        #   in.
        #
        # - Form a Meta class, inheriting from the Meta classes of the
        #   serializers of the model class's bases.
        #
        # - Inside the Meta class, merge the bases' `fields`, `exclude`,
        #   `read_only_fields` and `write_only_fields` fields. Just be glad I
        #   didn't use metametametaprogramming for this (metametaprogramming is
        #   bad enough!). BTW, it *really* doesn't bear thinking about. Make an
        #   effort to purge it from your mind now. Quick! Argh! Too late. :-(
        #
        # We try to minimise the stuff done inside this class, preferring to do
        # things in the metaclass, so that they will hold for manually created
        # serializers also.
        model_bases = model_class.__bases__

        is_root = model_class is CQRSModelMixin

        if not is_root and not all(issubclass(b, CQRSModelMixin)
                                   for b in model_bases):
            # There's nothing fundamentally wrong with this case, but it's
            # simpler to deny its existence for the moment. When it turns out
            # we need it at some point in the future, well, we'll implement it.
            raise NotImplementedError(
                "Sorry, {!r} has a mix of CQRS and non-CQRS bases and we can't"
                " cope with that yet. "
                "(Hint: all bases should derive from CQRSModelMixin.)"
                .format(model_class.__name__))

        # As far as I care at present, if it's the root it has no base classes
        # to worry about. Be careful about this if you're implementing the
        # above CQRS/non-CQRS blending, it will probably need to change to
        # considering model_bases and the filtered subset cqrs_model_bases
        # instead.
        if is_root:
            model_bases = ()

        # This might recurse, creating a serializer for a base class, should it
        # not have one specified. That doesn't matter, though, because
        # inheritance is a tree, so there's no dangerous recursion.
        serializer_bases = tuple(self[cls] for cls in model_bases)

        # Now we can set about creating the serializer. First step: the Meta
        # class for inside the serializer. There are a few special things:
        #
        # - Its bases must be the Meta classes of the model class's bases. This
        #   is a little uncommon, but not unheard of and will take care of most
        #   things that we don't know about.
        #
        # - But still, we must merge the bases' `fields`, `exclude`,
        #   `read_only_fields` and `write_only_fields` fields.
        #
        # Just be glad I didn't use metametametaprogramming for this
        # (metametaprogramming is bad enough!). BTW, it *really* doesn't bear
        # thinking about. Make an effort to purge it from your mind now. Quick!
        # Argh! Too late. :-(
        meta_bases = tuple(s.Meta for s in serializer_bases
                           if hasattr(s, 'Meta'))
        meta_attrs = {}
        for attr in ('fields', 'exclude', 'read_only_fields',
                     'write_only_fields'):
            set_value = False
            # set, not list; assumption: order doesn't matter. Otherwise it'd
            # be (for some fudged N) O(N^2) rather than O(N). (rest_framework
            # is more conscientious about order. It reckons it does matter.)
            value = set()
            for base_meta in meta_bases:
                if hasattr(base_meta, attr):
                    set_value = True
                    value.update(getattr(base_meta, attr))
            if set_value:
                meta_attrs[attr] = list(value)

        # Just to simplify matters, we will actually ensure we have Meta.fields
        # set so that we can append to it.
        meta_attrs.setdefault('fields', [])

        # Hold it right there! You didn't think we were *finished*, did you?
        # Oh, no! Certainly not! We've still got to add any new fields added in
        # this model class. Unfortunately, this part really is magic. Sorry
        # about that. You see, things are all mangled about in such a way that
        # we can't just conveniently determine which fields were specified in
        # the current class. It requires a bit more hunting around.

        meta_attrs['model'] = model_class
        # Yay! We survived! Now we have all we need for our Meta, we can go on
        # and make the rest. "The rest", fortunately, is pretty easy.

        # If the author went creating multiple fields with the same name in
        # different parts of inheritance tree: tough luck. We're not helping
        # you out of *that* hole. Things will probably break in undesirable (!)
        # ways.

        # We've already added fields that were present in the base classes'
        # serializers, so all we want to do now is add fields new to this model
        # class.

        # Select all the fields. Assuming field order doesn't matter.
        # NOT using model_class._meta.get_all_field_names() as that includes
        # many-to-many relations which are *probably* not desired and the
        # OneToOneField of subclasses and such. Also removing fields like
        # modela_ptr which are the polymorphic inheritance thingies.
        fields_to_add = set(f.name for f in model_class._meta.fields
                            if not f.name.endswith('_ptr'))

        for base in model_class.__bases__:
            # I know I said we don't cope with the mixed support issue, but
            # here it's easy to demonstrate what will need to be done...
            if issubclass(base, CQRSModelMixin):
                # Any fields that were present in a base CQRS class, we
                # naturally don't want to add.
                fields_to_add -= set(base._meta.get_all_field_names())
            # else: include all the fields (no reason to exclude them)

        for field in fields_to_add:
            if field not in meta_attrs['fields']:
                meta_attrs['fields'].append(field)

        # XXX: this is hard-coding a metaclass rather than inferring one from
        # serializer_bases. That is not good, but will probably do for now.
        return CQRSSerializerMeta(
            model_class.__name__ + 'AutoCQRSSerializer',
            serializer_bases,
            {'Meta': type('Meta', meta_bases + (object,), meta_attrs),
             '__module__': model_class.__module__,
             '__doc__': 'Automatically generated CQRS serializer for {}.'
                        .format(model_class.__name__)})


class CQRSSerializerMeta(serializers.SerializerMetaclass):
    """
    Metaclass for CQRS serializers, taking care of registration and field
    detection.
    """
    _register = SerializerRegister()

    def __new__(cls, name, bases, attrs):
        # There are certain conveniences and invariants that we wish to hold
        # for CQRS serializers.
        #
        # - Meta exists
        if 'Meta' not in attrs:
            attrs['Meta'] = type('Meta', (), {})
        meta = attrs['Meta']

        # - The superclasses are correct. You know, I call quite a few things
        #   in this code evil and magic; if I were asked to specify one as
        #   being the most evil and underhanded, this would be it without a
        #   doubt.
        if 'CQRSPolymorphicSerializer' in globals() and \
                bases == (CQRSPolymorphicSerializer,):
            # See tests.DSerializer for an explanation of the purpose of this.
            # Short version: so that manually specified fields get inherited
            # properly.
            bases = tuple(cls._register[base]
                          for base in meta.model.__bases__
                          if issubclass(base, CQRSPolymorphicModel)) or bases

        # - Meta.excludes does not exist
        if hasattr(meta, 'exclude'):
            # It might be a little tricky, but it can be done. But better to be
            # upfront about it than allow it to be broken.
            raise NotImplementedError(
                "CQRS polymorphic serializers can't cope with Meta.exclude "
                "yet.\n(There's nothing fundamentally wrong with it, it's "
                "just not implemented and will break the techniques in use.)\n"
                "Please use Meta.fields instead. Sorry.")

        # - Meta.fields exists and is a list
        if not hasattr(meta, 'fields'):
            meta.fields = []
        elif not isinstance(meta.fields, list):
            meta.fields = list(meta.fields)

        # This, then, is the canonical list, to which we must add all fields
        # (calculated or automatic) that must be included. Frankly, I don't
        # know why DRF doesn't do most of this itself (for manually specified
        # fields, at least), but it doesn't, so we must. And in a way that
        # won't break if they do start doing it.
        fields = meta.fields

        def append_field(f):
            # I know this is at least O(N). Yes, that is mildly bad.
            if f not in fields:
                fields.append(f)

        def prepend_field(f):
            # This one is *really* bad, probably O(N^2) or so.
            if f not in fields:
                fields.insert(0, f)

        # - Meta.fields includes all the manually specified fields
        for k, v in six.iteritems(attrs):
            if isinstance(v, Field):
                append_field(k)

        # - Meta.fields includes all the super serializers' Meta.fields values

        # Precondition: bases *must* have Meta.fields, prepopulated in the same
        # way and including all their fields. (This can be reconsidered if
        # necessary, e.g. if adding mixed CQRS + non-CQRS inheritance, but it
        # simplifies things a little.)
        # And just for a change, let's care about order. I don't know quite why
        # I'm doing this, really...
        for base in bases[::-1]:
            for field in base.Meta.fields[::-1]:
                prepend_field(field)

        # So now we're in the happy situation where you can not worry about who
        # you're inheriting from; all your bases' fields are belong to our
        # Meta.fields, plus all manually specified fields :-)
        # All subclasses will thus have field sets which are supersets of those
        # of their parent classes. This is sound subclassing. You can now write
        # a polymorphic serializer and only need to include the *new* fields.

        return super(CQRSSerializerMeta, cls).__new__(cls, name, bases, attrs)

    def __init__(self, *args, **kwargs):
        super(CQRSSerializerMeta, self).__init__(*args, **kwargs)

        # TODO: we probably need to check fields at this point.
        # TODO: what about subclasses of the serializer?
        model = getattr(self.Meta, 'model', None)
        if model is not None:
            CQRSSerializerMeta._register[model] = self


class CQRSSerializer(serializers.ModelSerializer):

    class Meta:
        model = CQRSModel
        fields = 'id', 'mongoID'


class CQRSPolymorphicSerializer(six.with_metaclass(CQRSSerializerMeta,
                                                   CQRSSerializer)):
    '''
    Serializer for Polymorphic Model
    '''

    def __init__(self, *args, **kwargs):
        if type(self) is CQRSPolymorphicSerializer:
            # This isn't meant to be a genuine serializer; it's just in it for
            # the to_native. This is *exceptionally* evil and voids all
            # warranties that the MIT license gave you. In fact, the
            # `self.fields = self.get_fields()` line will fail because the
            # model is abstract and so parts of it are not set up.
            return
        super(CQRSSerializer, self).__init__(*args, **kwargs)

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
