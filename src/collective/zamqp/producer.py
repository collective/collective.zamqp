# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the GPL license, see LICENCE.txt for more details.
#
# Copyright by Affinitic sprl
# Copyright (c) 2012 University of Jyväskylä
###
"""Producer utility base class"""

import threading

import grokcore.component as grok

from zope.component import getUtility, queryUtility, provideHandler

from collective.zamqp.interfaces import\
    IProducer, IBrokerConnection, IBeforeBrokerConnectEvent, ISerializer
from collective.zamqp.transactionmanager import VTM

from pika import BasicProperties
from pika.callback import CallbackManager

import logging
logger = logging.getLogger('collective.zamqp')

threadlocal = threading.local()  # storage for thread-safe attributes

# XXX: The threadlocal storage was made module-level attribute for debugging
# purporses (instance specific values are stored using repr() as their key),
# but should eventually be moved into an instance property.


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

    queue = None
    queue_durable = None
    queue_exclusive = False
    queue_arguments = {}

    auto_declare = True

    reply_to = None
    serializer = 'pickle'

    def __init__(self, connection_id=None, exchange=None, routing_key=None,
                 durable=None, exchange_type=None, exchange_durable=None,
                 queue=None, queue_durable=None, queue_exclusive = None,
                 queue_arguments=None, auto_declare=None, reply_to=None,
                 serializer=None):

        self._connection = None

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

        # routing_key
        if self.routing_key is None and routing_key is None:
            routing_key =\
                getattr(self, 'grokcore.component.directive.name', None)
        if routing_key is not None:
            self.routing_key = routing_key
        assert self.routing_key is not None,\
               u"Producer configuration is missing routing_key."

        # durable (and the default for exchange_durable)
        if durable is not None:
            self.durable = durable

        # exchange_type
        if exchange_type is not None:
            self.exchange_type = exchange_type
        # exchange_durable
        if exchange_durable is not None:
            self.exchange_durable = exchange_durable
        elif self.exchange_durable is None:
            self.exchange_durable = self.durable

        # queue
        if queue:
            self.queue = queue
        # queue_durable
        if queue_durable is not None:
            self.queue_durable = queue_durable
        elif self.queue_durable is None:
            self.queue_durable = self.durable
        # queue_exclusive
        if queue_exclusive is not None:
            self.queue_exclusive = queue_exclusive
        # queue_arguments
        if queue_arguments is not None:
            self.queue_arguments = queue_arguments

        # auto_declare
        if auto_declare is not None:
            self.auto_declare = auto_declare

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
            logger.warning(("Connection '%s' was not registered. "
                            "Producer '%s' cannot be connected."),
                            self.connection_id, self.routing_key)

    def on_channel_open(self, channel):
        self._channel = channel

        if self.auto_declare and self.exchange\
            and not self.exchange.startswith('amq.'):
            self.declare_exchange()
        elif self.auto_declare and self.queue:
            self.declare_queue()
        else:
            self.on_ready_to_publish()

    def declare_exchange(self):
        self._channel.exchange_declare(exchange=self.exchange,
                                       type=self.exchange_type,
                                       durable=self.exchange_durable,
                                       auto_delete=not self.exchange_durable,
                                       callback=self.on_exchange_declared)

    def on_exchange_declared(self, frame):
        logger.info("Producer declared exchange '%s'", self.exchange)
        if self.auto_declare and self.queue:
            self.declare_queue()
        else:
            self.on_ready_to_publish()

    def declare_queue(self):
        self._channel.queue_declare(queue=self.queue,
                                    durable=self.queue_durable,
                                    exclusive=self.queue_exclusive,
                                    auto_delete=not self.queue_durable,
                                    arguments=self.queue_arguments,
                                    callback=self.on_queue_declared)

    def on_queue_declared(self, frame):
        logger.info("Producer declared queue '%s'", self.queue)
        if self.auto_declare and self.exchange:
            self.bind_queue()
        else:
            self.on_ready_to_publish()

    def bind_queue(self):
        self._channel.queue_bind(exchange=self.exchange, queue=self.queue,
                                 routing_key=self.routing_key or self.queue,
                                 callback=self.on_queue_bound)

    def on_queue_bound(self, frame):
        logger.info("Producer bound queue '%s' to exchange '%s'",
                    self.queue, self.exchange)
        self.on_ready_to_publish()

    def on_ready_to_publish(self):
        logger.info(("Producer ready to publish to exchange '%s' "
                     "with routing key '%s'"),
                    self.exchange, self.routing_key)
        self._callbacks.process(0, "_on_ready_to_publish", self)

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
            correlation_id=str(correlation_id), reply_to=reply_to,
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

    def _basic_publish(self, **kwargs):
        retry_constructor = lambda func, kwargs: lambda: func(**kwargs)

        if getattr(self._connection, "is_open", False)\
            and getattr(self, '_channel', None):
            self._channel.basic_publish(**kwargs)
            return True

        elif self.durable:
            logger.warning(('No connection. Durable message will be left to '
                            'wait for the new connection: %s'), kwargs)
            retry_callback = retry_constructor(self._basic_publish, kwargs)
            self._callbacks.add(0, '_on_ready_to_publish', retry_callback)
            # XXX: Pika's CallbackManager is not threadsafe and this method
            # is being called from the worker threads. Needs threadlock!
            return False

    def _tx_commit(self):
        if getattr(self._connection, "is_open", False)\
            and getattr(self, '_channel', None):
            self._channel.tx_commit()
        else:
            logger.warning('No connection. Tx.Commit could not be sent.')

    def _begin(self):
        self._pending_messages = []

    def _abort(self):
        self._pending_messages = None

    def _finish(self):
        while self._pending_messages:
            self._basic_publish(**self._pending_messages.pop())
        if getattr(self._connection, "tx_select", False):
            self._tx_commit()  # minimal support for transactional channel

    # Define thread-safe VTM._v_registered:

    def _get_v_registered(self):
        if hasattr(threadlocal, "collective_zamqp_v_registered"):
            return threadlocal.collective_zamqp_v_registered.get(str(self))
        else:
            return 0

    def _set_v_registered(self, value):
        if not hasattr(threadlocal, "collective_zamqp_v_registered"):
            threadlocal.collective_zamqp_v_registered = {}
        threadlocal.collective_zamqp_v_registered[str(self)] = value

    _v_registered = property(_get_v_registered, _set_v_registered)

    # Define thread-safe VMT._v_finalize:

    def _get_v_finalize(self):
        if hasattr(threadlocal, "collective_zamqp_v_finalize"):
            return threadlocal.collective_zamqp_v_finalize.get(str(self))
        else:
            return 0

    def _set_v_finalize(self, value):
        if not hasattr(threadlocal, "collective_zamqp_v_finalize"):
            threadlocal.collective_zamqp_v_finalize = {}
        threadlocal.collective_zamqp_v_finalize[str(self)] = value

    _v_finalize = property(_get_v_finalize, _set_v_finalize)

    # Define thread-safe self._pending_messages:

    def _get_pending_messages(self):
        if hasattr(threadlocal, "collective_zamqp_pending_messages"):
            return threadlocal.collective_zamqp_pending_messages.get(str(self))
        else:
            return None

    def _set_pending_messages(self, value):
        if not hasattr(threadlocal, "collective_zamqp_pending_messages"):
            threadlocal.collective_zamqp_pending_messages = {}
        threadlocal.collective_zamqp_pending_messages[str(self)] = value

    _pending_messages = property(_get_pending_messages, _set_pending_messages)


# BBB for affinitic.zamqp

from zope.deprecation import deprecated

Producer.send = deprecated(Producer.publish,
                           ('Producer.send is no more. '
                            'Please, use Producer.publish instead.'))
