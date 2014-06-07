# here for safe keeping...

def update(self, request, *args, **kwargs):
    partial = kwargs.pop('partial', False)
    self.object = self.get_object_or_none()

    if self.object is None:
        created = True
        save_kwargs = {'force_insert': True}
        success_status_code = status.HTTP_201_CREATED
    else:
        created = False
        save_kwargs = {'force_update': True}
        success_status_code = status.HTTP_200_OK

    serializer = self.get_serializer(self.object, data=request.DATA,
                                     files=request.FILES, partial=partial)

    # This is getting around something wrong happening in the CQRSPolyMorphic
    # from_native method.
    obj = serializer.object

    # During this call, we lose reference to the serializer.object
    # because the overridden from_native method fails to send it back
    # to us in self.errors
    if serializer.is_valid():
        try:
            # restore the reference after its been mutated
            serializer.object = obj
            self.pre_save(serializer.object)
        except ValidationError as err:
            # full_clean on model instance may be called in pre_save, so we
            # have to handle eventual errors.
            return Response(err.message_dict, status=status.HTTP_400_BAD_REQUEST)


        self.object = serializer.save(**save_kwargs)

        # AWESOME HAX WTF WTF
        # self.object is still the same as before. Why?

        # Something's amiss with Chris' fancy pants CQRS Auto Polymorphic Serializer magix
        # and the rabbit seems to be hiding at the bottom of the hat.
        # So here, we brutally fish out the data from the request and hope that it saves.
        # to hell with complex data types like DateTime...
        # I'm sure this will complain loudly at the right time.

        try:
            data = request.DATA
            data.pop('pk')
            data.pop('type')
            print "data: {}".format(data)
            for key, value in data.iteritems():

                attr = getattr(self.object, key)
                klass = attr.__class__

                if hasattr(klass, 'objects'):
                    kwargs = {}

                    if(isinstance(value, dict)):
                        # if we have a dict, we have full serialized form of the object
                        # so let's do a little parsing.
                        if '_id' in value.keys():
                            # we have a mongo style _id, let's change it
                            value['id'] = value.pop('_id')
                        kwargs = value
                    else:
                        # else, we're trusting that we have an id field
                        kwargs = {'pk': value}

                    # Now let's get the instance and reassign it as value
                    try:
                        value = klass.objects.get(**kwargs)
                    except klass.DoesNotExist, e:
                        serializer._errors[key] = e.message
                        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                setattr(self.object, key, value)

            # And what about m2m stuffs? Oh my.
            # Oh well, let's save it for now and see what breaks!
            self.object.save()

        except Exception, e:
            serializer._errors['operation'] = e.message
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        self.post_save(self.object, created=created)
        return Response(serializer.data, status=success_status_code)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)