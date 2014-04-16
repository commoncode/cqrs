from __future__ import absolute_import

from collections import namedtuple
from ..backend import PolymorphicBackendBase


ADD = 'ADD'
DELETE = 'DELETE'
CHANGE = 'CHANGE'

Action = namedtuple('Action', ('action', 'collection', 'doc_id', 'doc'))


class OpLogBackend(PolymorphicBackendBase):
    """
    A backend that merely keeps an log of all operations on it.

    You can retrieve and clear the log with :meth:`flush_oplog`.
    """

    def flush_oplog(self):
        """
        Retrieve the list of logged operations and return it, clearing the
        backend's list at the same time.
        """
        oplog = self.oplog
        self.oplog = []
        return oplog

    def __init__(self, name=None):
        super(OpLogBackend, self).__init__(name)
        self.oplog = []

    def log(self, action, collection, doc_id, doc=None):
        """Make an oplog entry."""
        self.oplog.append(Action(action, collection, doc_id, doc))

    def deleted(self, collection, doc_id):
        self.log(DELETE, collection, doc_id)

    def added(self, collection, doc_id, doc):
        self.log(ADD, collection, doc_id, doc)

    def changed(self, collection, doc_id, doc):
        self.log(CHANGE, collection, doc_id, doc)

    # get_doc and sync_collection are not implemented; they are considered out
    # of scope for the tests.
