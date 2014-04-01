from django.db import models

from bson.objectid import ObjectId


class CQRSModelMixin(models.Model):
    """
    This model allows CQRSSerializer plugins to be effective by
    assigning mongoID.

    XXX in the case of a non-mongo architecture; this would need
    to be optioned out.
    """

    mongoID = models.CharField(max_length=24)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.mongoID:
            self.mongoID = str(ObjectId())
        super(CQRSModelMixin, self).save(*args, **kwargs)


