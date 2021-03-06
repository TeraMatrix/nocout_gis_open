# nqueue is nocout cache implmentation
# based on REDIS & Django-Redis & Python Redis
# would provide dropin replacement for QUEUE python

import time

try:
    import cPickle as pickle
except ImportError:
    import pickle

from django.conf import settings

from redis import StrictRedis, ConnectionError, ResponseError

REDIS_QUEUE_HOST = getattr(settings, 'REDIS_HOST', 'localhost')
REDIS_QUEUE_PORT = getattr(settings, 'REDIS_PORT', 6379)
REDIS_QUEUE_DB = getattr(settings, 'REDIS_DB', 0)
REDIS_QUEUE_URL = getattr(settings, 'REDIS_QUEUE_URL',
                          'redis://' + str(REDIS_QUEUE_HOST) + ':' + str(REDIS_QUEUE_PORT) + '/' + str(REDIS_QUEUE_DB)
                          )

QUEUES = getattr(settings,
                 'QUEUES', {
                     'default': {
                         'LOCATION': REDIS_QUEUE_URL,
                         'TIMEOUT': 60,
                         'NAMESPACE': 'noc:queue:'
                     }
                 })

class NQueue(object):
    """
    nqueue class for nocout
    """
    def __init__(self, qconf=None, qname='nocout', serializer=pickle):
        """The default connection parameters are: host='localhost', port=6379, db=0"""

        self._settings = QUEUES
        self._params = self._settings.get(qconf, self._settings.get('default'))

        # TODO: Support all the configuration parameters for REDIS
        self._timeout = self._params.get('TIMEOUT', 60)
        self._url = self._params.get('LOCATION', REDIS_QUEUE_URL)
        self._namespace = self._params.get('NAMESPACE', 'noc:queue:')

        self.serializer = serializer
        # all queue names must be different
        self.qkey = '%s:%s:%s' % (self._namespace, qname, time.time())

        self.__redis = StrictRedis.from_url(self._url)

    def __len__(self):
        return self.__redis.llen(self.qkey)

    @property
    def key(self):
        """Return the key name used to store this queue in Redis."""
        return self.qkey

    def ping(self):
        """use REDIS ping to check the connection. _NQueue__redis.ping()"""
        try:
            self._NQueue__redis.ping()
            return True
        except ConnectionError:
            return False
        except ResponseError:
            return False

    def clear(self):
        """Clear the queue of all messages, deleting the Redis key."""
        self.__redis.delete(self.key)

    def qsize(self):
        """Return the approximate size of the queue."""
        return self.__len__()

    def empty(self):
        """Return True if the queue is empty, False otherwise."""
        return True if self.qsize() == 0 else False

    def get(self, block=True, timeout=None):
        """Return a message from the queue. Example:

        :param block: whether or not to wait until a msg is available in
            the queue before returning; ``False`` by default
        :param timeout: when using :attr:`block`, if no msg is available
            for :attr:`timeout` in seconds, give up and return ``None``
        """
        if block:
            if timeout is None:
                timeout = 0
            msg = self.__redis.blpop(self.key, timeout=timeout)
            if msg is not None:
                msg = msg[1]
        else:
            msg = self.__redis.lpop(self.key)
        if msg is not None and self.serializer is not None:
            msg = self.serializer.loads(msg)
        return msg

    def put(self, *msgs):
        """Put one or more messages onto the queue. Example:

        To put messages onto the queue in bulk, which can be significantly
        faster if you have a large number of messages:

        """
        if self.serializer is not None:
            msgs = map(self.serializer.dumps, msgs)
        self.__redis.rpush(self.key, *msgs)

    def get_nowait(self):
        """Equivalent to get(False)."""
        return self.get(False)
