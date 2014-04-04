from django.db import models
from ..models import CQRSPolymorphicModel


# TODO: at present pretty much all the tests are for polymorphic classes.
# We need non-polymorphic tests.

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
            fields['mongoID'] = model_instance.mongoID
            fields['type'] = '{}.{}'.format(type(model_instance).__module__,
                                            type(model_instance).__name__)
        return fields

    def as_test_serialized(self):
        return self.test_data(self)

    @classmethod
    def create_test_instance(cls):
        return cls.objects.create(**cls.test_data())

    return type(base)(
        'Model' + prefix.upper(),
        (base,),
        {
            'field_{}1'.format(prefix): models.CharField(max_length=50),
            'field_{}2'.format(prefix): models.CharField(max_length=50),
            'calc_{}3'.format(prefix):
            lambda self: 'from calc_{}3'.format(prefix),
            'prefix': prefix,
            'test_data': test_data,
            'as_test_serialized': as_test_serialized,
            'create_test_instance': create_test_instance,
            '__module__': __name__,
        })


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
