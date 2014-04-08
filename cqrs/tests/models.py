from django.db import models
from ..models import CQRSModel, CQRSPolymorphicModel


def standard_model_test_methods():
    '''
    ... too lazy to write this line.

    Ensure you define test_data yourself.

    Usage: ``locals().update(standard_model_test_methods())``.
    '''

    def as_test_serialized(self):
        return self.test_data(self)

    @classmethod
    def create_test_instance(cls):
        return cls.objects.create(**cls.test_data())

    return {'as_test_serialized': as_test_serialized,
            'create_test_instance': create_test_instance}


def maybe_add_id(model_instance, fields):
    if model_instance:
        fields['id'] = model_instance.id
    return fields


def make(prefix, base):
    '''
    Generate things.

    Usage::

        ModelAA = make('aa', ModelA)

    This is equivalent to::

        class ModelAA(ModelA):
            field_aa1 = models.CharField(max_length=50)
            field_aa2 = models.CharField(max_length=50)

            def calc_aa3(self):
                return 'from calc_aa3'
    '''

    @classmethod
    def test_data(cls, model_instance=None):
        '''
        Produce a dictionary of the test data, in serialized form if a
        model instance is given (representing what it is expected
        serializing the instance will yield), or as the keyword arguments
        for ``Model.objects.create()`` if no instance is given.
        '''
        fields = {}
        for base in cls.__mro__:
            if base is CQRSPolymorphicModel:
                break
            assert base.__name__.startswith('Model')
            fields['field_{}1'.format(base.prefix)] = base.prefix
            if base.prefix.endswith('m'):  # Manual serializer
                if model_instance:
                    fields['manual_{}3'.format(base.prefix)] = \
                        'from calc_{}3'.format(base.prefix)
            else:  # Automatic serializer
                fields['field_{}2'.format(base.prefix)] = base.prefix.upper()
        if model_instance:
            fields['id'] = model_instance.id
            fields['type'] = '{}.{}'.format(type(model_instance).__module__,
                                            type(model_instance).__name__)
        return fields

    attrs = {
        'field_{}1'.format(prefix): models.CharField(max_length=50),
        'field_{}2'.format(prefix): models.CharField(max_length=50),
        'calc_{}3'.format(prefix):
        lambda self: 'from calc_{}3'.format(prefix),
        'prefix': prefix,
        'test_data': test_data,
        '__module__': __name__,
    }
    attrs.update(standard_model_test_methods())
    return type(base)('Model' + prefix.upper(), (base,), attrs)


# Naming scheme: ending with 'A' means the serializer for that class is
# automatic, and with 'M' means there is a manually specified serializer.
# We'll go down to three levels; that should take care of everything.
ModelA = make('a', CQRSPolymorphicModel)
ModelAA = make('aa', ModelA)
ModelAAA = make('aaa', ModelAA)
ModelAAM = make('aam', ModelAA)
ModelAM = make('am', ModelA)  # good morning
ModelAMA = make('ama', ModelAM)
ModelAMM = make('amm', ModelAM)
ModelM = make('m', CQRSPolymorphicModel)
ModelMA = make('ma', ModelM)
ModelMAA = make('maa', ModelMA)
ModelMAM = make('mam', ModelMA)
ModelMM = make('mm', ModelM)
ModelMMA = make('mma', ModelMM)
ModelMMM = make('mmm', ModelMM)


# OK, that's enough polymorphic testing.

class BoringModel(CQRSModel):
    # This one has nothing distinctive about it. It's just "average".
    # *Very* average. Especially its poetry.
    roses = models.CharField(default='red', max_length=50)
    violets = models.CharField(default='blue', max_length=50)

    def silly_poetry(self):
        return 'Roses are {},\n\
                Violets are {},\n\
                This pseudo-poem is generated\n\
                With a little user input.'.format(self.roses, self.violets)

    @classmethod
    def test_data(cls, model_instance=None):
        # Yeah, I wrote it this way on purpose, for the fun of it. Ugly, innit?
        fields = maybe_add_id(model_instance, {
            'violets': 'red',
        })
        fields.update({
            'daft_poem': model_instance.silly_poetry(),
        } if model_instance else {
            'roses': 'blue',
        })
        return fields

    locals().update(standard_model_test_methods())


class DryIngredientsMixin(models.Model):
    sugar = models.IntegerField()
    flour = models.IntegerField()

    class Meta:
        abstract = True


class OneMixingBowl(CQRSModel, DryIngredientsMixin):
    # This one will get a serializer.
    water = models.IntegerField()
    oil = models.IntegerField()

    @property
    def total(self):
        # Let's ignore absorption
        return self.water + self.oil + self.sugar + self.flour

    @classmethod
    def test_data(cls, model_instance=None):
        fields = maybe_add_id(model_instance, {
            'water': 100,
            'sugar': 1000,
        })
        if model_instance:  # Only include total when serializing
            fields.update({
                'total': model_instance.total,
            })
        else:  # Only include these fields when creating an instance
            fields.update({
                'oil': 10,
                'flour': 1,
            })
        return fields

    locals().update(standard_model_test_methods())


class AnotherMixingBowl(CQRSModel, DryIngredientsMixin):
    # This one will get a partially automatic serializer.
    water = models.IntegerField()
    oil = models.IntegerField()

    @classmethod
    def test_data(cls, model_instance=None):
        # No serializer specified; all of the fields should be included.
        return maybe_add_id(model_instance, {
            'water': 100,
            'oil': 10,
            'sugar': 1000,
            'flour': 1,
        })

    locals().update(standard_model_test_methods())


class AutomaticMixer(CQRSModel, DryIngredientsMixin):
    # This one will *not* get a serializer. And so it will refuse to work,
    # because of the existence mixin.

    @classmethod
    def test_data(cls, model_instance=None):
        return maybe_add_id(model_instance, {
            'sugar': 1000,
            'flour': 1,
        })

    locals().update(standard_model_test_methods())
