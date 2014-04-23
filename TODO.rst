There are still a handful of things that need (for some value of “need”) doing.

- Implement views for making a nice quick REST API which will map URLS of the
  form ``/foo/<collection_name>`` onto DRF views. (This should be done outside
  of cqrs, in cqrs-renormalize.)

- Test automatic derivation of collections.

- Automatically add collections to a backend. (It really grates how we have
  this ``cqrs.mongo.mongodb`` hardcoded everywhere. It's fragile, too.)

- Implement some form of "tag" functionality, whereby we can have multiple
  serializers (and in turn collections) with a tag to discriminate between
  them. If no tag is specified, use ``None``, indicating a default serializer.
  While it would be possible to change the "which fields do we use?" rules to
  fall back to a default serializer, I think that is risky behaviour. I suggest
  completely distinct trees with absolutely nothing shared. It will be easier
  to reason about that way.
