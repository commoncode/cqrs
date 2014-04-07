from denormalize.backend.base import BackendBase


class PolymorphicBackendBase(BackendBase):
    """
    A polymorphic backend base, which sets up listeners appropriate for
    inheritance in Django. It has no dependency on CQRS stuff, but is best used
    with django-polymorphic, so that you get instances of the right type.

    This can be safely used as a mixin, too.
    """

    def _setup_listeners(self, collection):
        # This is something that can *almost* be done in the collection, but
        # not quite. But really, doing it here is the right place, anyway.
        # Tests ensure that this fairly fragile thing doesn't break unnoticed.
        super(PolymorphicBackendBase, self)._setup_listeners(collection)

        self._setup_subclass_listeners(collection, collection.model)

    def _setup_subclass_listeners(self, collection, model):
        for submodel in model.__subclasses__():
            # Yeah, this adds leaves before their parents, but that's fine.
            # Order don't matter.
            self._setup_subclass_listeners(collection, submodel)

            if submodel._meta.abstract or submodel._meta.proxy:
                # Skip any abstract or proxy classes. (Can you have an abstract
                # child of a concrete class? Dunno, but might as well include
                # the condition Just In Case.)
                continue
            self._add_listeners(collection=collection,
                                filter_path=None,
                                submodel=submodel,
                                info=None)

            # Hello again. You hate me now, for all this underhanded trickery
            # that I do, don't you? Well, I'm at it again.
            #
            # This time, the problem is that, while the save handler does not
            # bubble upwards, the delete handler *does* bubble upwards.
            #
            # That is, given class Super(Model) and class Sub(Super), a save
            # event on Sub does *not* bubble up to Super, but the delete
            # signals *do* bubble up, so that deleting a Sub object triggers
            # pre/post delete signals for a Sub instance with a Sub sender, and
            # then for a Super instance (!) with a Super sender.
            #
            # It'd probably be OK to leave it all registered beyond what's
            # necessary and let deletion just fail silently, but it's not hard
            # to work around it in this case, by deleting the listener function
            # that django-denormalize made, and that's a preferable workaround.
            # (Deleting the listener works because signals uses weak refs.)
            #
            # This "fix" is fragile, hence the assertions and the test suite
            # which will catch things if this stops doing what's intended.
            # I'm sorry to have put you through all this, but I assure you, I
            # did mean well.
            #
            # See also https://code.djangoproject.com/ticket/18094 and
            # https://code.djangoproject.com/ticket/9318 for more discussion of
            # the underlying problem. (Concensus is that it's a design bug.)
            assert self._listeners.pop().__name__ == 'post_delete'
            assert self._listeners.pop().__name__ == 'pre_delete'
