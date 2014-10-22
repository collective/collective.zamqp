# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyright (c) 2012 University of Jyväskylä and Contributors.
###
# This module is a derivate of affinitic.zamqp.publisher.
#
# Copyright by Affinitic sprl
###
"""Producer utility base class"""

import threading

import grokcore.component as grok

from zope.component import getUtility, queryUtility, provideHandler

from collective.zamqp.utils import logger
from collective.zamqp.interfaces import\
    IProducer, IBrokerConnection, IBeforeBrokerConnectEvent, ISerializer
from collective.zamqp.transactionmanager import VTM
from collective.zamqp.connection import BlockingChannel

from pika import BasicProperties
from pika.callback import CallbackManager


class Producer(grok.GlobalUtility, VTM):
    """Producer utility base class"""

    grok.baseclass()
    grok.implements(IProducer)

    connection_id = None

    exchange = ''
    routing_key = None
    durable = True

    exchange_type = 'direct'
    exchange_durable = None
    exchange_auto_delete = None
    exchange_auto_declare = None

    queue = None
    queue_durable = None
    queue_auto_delete = None
    queue_exclusive = False
    queue_arguments = {}
    queue_auto_declare = None

    auto_declare = True
    auto_delete = None

    reply_to = None
    serializer = 'pickle'

    def __init__(self, connection_id=None, exchange=None, routing_key=None,
                 durable=None, exchange_type=None, exchange_durable=None,
                 exchange_auto_delete=None, exchange_auto_declare=None,
                 queue=None, queue_durable=None, queue_auto_delete=None,
                 queue_exclusive=None, queue_arguments=None,
                 queue_auto_declare=None, auto_declare=None, auto_delete=None,
                 reply_to=None, serializer=None):

        self._connection = None
        self._queue = None  # will default to self.queue
        self._lock = threading.Lock()
        self._threadlocal = threading.local()  # to thread-safe some attributes

        # Allow class variables to provide defaults for:

        # connection_id
        if connection_id is not None:
            self.connection_id = connection_id
        assert self.connection_id is not None,\
            u"Producer configuration is missing connection_id."

        # exchange
        if exchange is not None:
            self.exchange = exchange
        assert self.exchange is not None,\
            u"Producer configuration is missing exchange."

        # durable (and the default for exchange/queue_durable)
        if durable is not None:
            self.durable = durable

        # auto_delete (and the default for exchange/queue_auto_delete)
        if auto_delete is not None:
            self.auto_delete = auto_delete
        elif self.auto_delete is None:
            self.auto_delete = not self.durable

        # exchange_type
        if exchange_type is not None:
            self.exchange_type = exchange_type
        # exchange_durable
        if exchange_durable is not None:
            self.exchange_durable = exchange_durable
        elif self.exchange_durable is None:
            self.exchange_durable = self.durable
        # exchange_auto_delete
        if exchange_auto_delete is not None:
            self.exchange_auto_delete = exchange_auto_delete
        elif self.exchange_auto_delete is None:
            self.exchange_auto_delete = self.auto_delete

        # queue
        if queue is not None:
            self._queue = self.queue = queue
        # queue_durable
        if queue_durable is not None:
            self.queue_durable = queue_durable
        elif self.queue_durable is None:
            self.queue_durable = self.durable
        # queue_auto_delete
        if queue_auto_delete is not None:
            self.queue_auto_delete = queue_auto_delete
        elif self.queue_auto_delete is None:
            self.queue_auto_delete = self.auto_delete
        # queue_exclusive
        if queue_exclusive is not None:
            self.queue_exclusive = queue_exclusive
        if self.queue_exclusive is True:
            self.queue_durable = False
            self.queue_auto_delete = True
        # queue_arguments
        if queue_arguments is not None:
            self.queue_arguments = queue_arguments

        # routing_key
        if self.routing_key is None and routing_key is None:
            routing_key =\
                getattr(self, 'grokcore.component.directive.name', None)
        if routing_key is not None:
            self.routing_key = routing_key
        elif self.routing_key is None:
            if self.queue is not None:
                self.routing_key = self.queue
            elif self.exchange_type == 'fanout':
                self.routing_key = '*'
        assert self.routing_key is not None,\
            u"Producer configuration is missing routing_key."

        # auto_declare
        if auto_declare is not None:
            self.auto_declare = auto_declare
        if exchange_auto_declare is not None:
            self.exchange_auto_declare = exchange_auto_declare
        elif self.exchange_auto_declare is None:
            self.exchange_auto_declare = self.auto_declare
        if queue_auto_declare is not None:
            self.queue_auto_declare = queue_auto_declare
        elif self.queue_auto_declare is None:
            self.queue_auto_declare = self.auto_declare

        # reply_to
        if reply_to is not None:
            self.reply_to = reply_to

        # serializer
        if serializer is not None:
            self.serializer = serializer

        # initialize callbacks
        self._callbacks = CallbackManager()  # callbacks are NOT thread-safe

        # subscribe to the connect initialization event
        provideHandler(self.on_before_broker_connect,
                       [IBeforeBrokerConnectEvent])

    def on_before_broker_connect(self, event=None):
        self._connection = queryUtility(IBrokerConnection,
                                        name=self.connection_id)
        if self._connection:
            self._connection.add_on_channel_open_callback(self.on_channel_open)
        else:
            logger.warning(u"Connection '%s' was not registered. "
                           u"Producer '%s' cannot be connected.",
                           self.connection_id, self.routing_key)

    def on_channel_open(self, channel):
        self._channel = channel

        if self.exchange_auto_declare and self.exchange\
                and not self.exchange.startswith('amq.'):
            self.declare_exchange()
        elif self.queue_auto_declare and self.queue is not None\
                and not self.queue.startswith('amq.'):
            self.declare_queue()
        else:
            self.on_ready_to_publish()

    def declare_exchange(self):
        self._channel.exchange_declare(exchange=self.exchange,
                                       type=self.exchange_type,
                                       durable=self.exchange_durable,
                                       auto_delete=self.exchange_auto_delete,
                                       callback=self.on_exchange_declared)

    def on_exchange_declared(self, frame):
        logger.default(u"Producer declared exchange '%s' on connection '%s'",
                       self.exchange, self.connection_id)
        if self.queue_auto_declare and self.queue is not None\
                and not self.queue.startswith('amq.'):
            self.declare_queue()
        else:
            self.on_ready_to_publish()

    def declare_queue(self):
        self._channel.queue_declare(queue=self.queue,
                                    durable=self.queue_durable,
                                    exclusive=self.queue_exclusive,
                                    auto_delete=self.queue_auto_delete,
                                    arguments=self.queue_arguments,
                                    callback=self.on_queue_declared)

    def on_queue_declared(self, frame):
        self._queue = frame.method.queue  # get the real queue name
        logger.default(u"Producer declared queue '%s' on connection '%s'",
                       self._queue, self.connection_id)
        if self.auto_declare and self.exchange:
            self.bind_queue()
        else:
            self.on_ready_to_publish()

    def bind_queue(self):
        self._channel.queue_bind(exchange=self.exchange, queue=self._queue,
                                 routing_key=self.routing_key or self._queue,
                                 callback=self.on_queue_bound)

    def on_queue_bound(self, frame):
        logger.default(u"Producer bound queue '%s' to exchange '%s' "
                       u"on connection '%s'",
                       self._queue, self.exchange, self.connection_id)
        self.on_ready_to_publish()

    def on_ready_to_publish(self):
        logger.default(u"Producer ready to publish to exchange '%s' "
                       u"with routing key '%s' on connection '%s'",
                       self.exchange, self.routing_key, self.connection_id)
        self._callbacks.process(0, "_on_ready_to_publish", self)

    @property
    def is_connected(self):
        if getattr(self._connection, "is_open", False)\
                and getattr(self, '_channel', None):
            return True
        else:
            return False

    def register(self):
        self._register()

    def publish(self, message, exchange=None, routing_key=None,
                mandatory=False, immediate=False,
                content_type=None, content_encoding=None,
                headers=None, delivery_mode=None, priority=None,
                correlation_id=None, reply_to=None, expiration=None,
                message_id=None, timestamp=None, type=None, user_id=None,
                app_id=None, cluster_id=None, serializer=None):

        exchange = exchange or self.exchange
        routing_key = routing_key or self.routing_key
        reply_to = reply_to or self.reply_to
        serializer = serializer or self.serializer

        if correlation_id is not None:
            correlation_id = str(correlation_id)

        if serializer and not content_type:
            util = getUtility(ISerializer, name=serializer)
            content_type = util.content_type
            message = util.serialize(message)
        elif not content_type:
            content_type = 'text/plain'

        if delivery_mode is None:
            if not self.durable:
                delivery_mode = 1  # message is transient
            else:
                delivery_mode = 2  # message is persistent

        properties = BasicProperties(
            content_type=content_type, content_encoding=content_encoding,
            headers=headers, delivery_mode=delivery_mode, priority=priority,
            correlation_id=correlation_id, reply_to=reply_to,
            expiration=expiration, message_id=message_id, timestamp=timestamp,
            type=type, user_id=user_id, app_id=app_id, cluster_id=cluster_id)

        msg = {
            'exchange': exchange,
            'routing_key': routing_key,
            'body': message,
            'properties': properties,
        }

        if self.registered():
            self._pending_messages.insert(0, msg)
        elif self._basic_publish(**msg) and self._connection.tx_select:
            self._tx_commit()  # minimal support for transactional channel

    def __len__(self):
        """Return message count of the target queue"""
        # XXX: Producer knows it target queue only, if it's explicitly
        # set in its definition. Otherwise self._queue is None
        assert self._queue, "Sorry, producer doesn't know its target queue."
        with BlockingChannel(self.connection_id) as channel:
            frame = channel.queue_declare(queue=self._queue,
                                          durable=self.queue_durable,
                                          exclusive=self.queue_exclusive,
                                          auto_delete=self.queue_auto_delete,
                                          arguments=self.queue_arguments)
            return frame.method.message_count

    def _basic_publish(self, **kwargs):
        retry_constructor = lambda func, kwargs: lambda: func(**kwargs)

        if getattr(self._connection, "is_open", False)\
                and getattr(self, '_channel', None):
            self._channel.basic_publish(**kwargs)
            return True

        elif getattr(kwargs.get("properties"), "delivery_mode", 1) == 2:
            logger.warning(u"No connection. Durable message was left into "
                           u"volatile memory to wait for a new connection "
                           u"'%s'", kwargs)
            retry_callback = retry_constructor(self._basic_publish, kwargs)
            with self._lock:
                self._callbacks.add(0, '_on_ready_to_publish', retry_callback)
            # XXX: ^^^ When connection is down, durable messages should be
            # stored in ZODB to prevent losing them, e.g. because of restart.
            return False

    def _tx_commit(self):
        if getattr(self._connection, "is_open", False)\
                and getattr(self, '_channel', None):
            self._channel.tx_commit()
        else:
            logger.warning(u'No connection. Tx.Commit was not sent')

    def _begin(self):
        self._pending_messages = []

    def _abort(self):
        self._pending_messages = None

    def _finish(self):
        while self._pending_messages:
            self._basic_publish(**self._pending_messages.pop())
        if getattr(self._connection, "tx_select", False):
            self._tx_commit()  # minimal support for transactional channel

    # Define threadlocal VTM._v_registered:

    def _get_v_registered(self):
        return getattr(self._threadlocal, "_v_registered", 0)

    def _set_v_registered(self, value):
        self._threadlocal._v_registered = value

    _v_registered = property(_get_v_registered, _set_v_registered)

    # Define threadlocal VTM._v_finalize:

    def _get_v_finalize(self):
        return getattr(self._threadlocal, "_v_finalize", 0)

    def _set_v_finalize(self, value):
        self._threadlocal._v_finalize = value

    _v_finalize = property(_get_v_finalize, _set_v_finalize)

    # Define threadlocal self._pending_messages:

    def _get_pending_messages(self):
        return getattr(self._threadlocal, "_pending_messages", None)

    def _set_pending_messages(self, value):
        self._threadlocal._pending_messages = value

    _pending_messages = property(_get_pending_messages, _set_pending_messages)


# BBB for affinitic.zamqp

from zope.deprecation import deprecated

Producer.send = deprecated(Producer.publish,
                           ('Producer.send is no more. '
                            'Please, use Producer.publish instead.'))
