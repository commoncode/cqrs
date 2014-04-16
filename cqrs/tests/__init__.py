# Ensure these are all imported, so that if you specify a subset of the tests,
# it can't go doing the wrong thing somehow (e.g. not picking up the correct
# serializer and so producing an automatic one)
from . import backend
from . import collections
from . import models
from . import serializers
from . import test_collections
from . import test_serializers
