# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyright (c) 2012 University of Jyväskylä and Contributors.
###
# This module is a derivate of affinitic.zamqp.consumer.
#
# Copyright by Affinitic sprl
###
"""Consumer utility base class"""

import datetime
import sys
import transaction

import grokcore.component as grok

from AccessControl.SecurityManagement import setSecurityManager
from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import getSecurityManager

from ZODB.POSException import ConflictError

from zope.interface import implements, alsoProvides
from zope.publisher.interfaces import IPublishTraverse
from zope.component import createObject, queryUtility
from zope.event import notify

try:
    from zope.component.hooks import getSite
    getSite  # pyflakes
except ImportError:  # BBB
    from zope.site.hooks import getSite

from Products.Five.browser import BrowserView

from collective.zamqp.utils import logger
from collective.zamqp.interfaces import IConsumer, IErrorHandler
from collective.zamqp.connection import BlockingChannel


class Consumer(grok.GlobalUtility):
    """Consumer utility base class"""

    grok.baseclass()
    grok.implements(IConsumer)

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

    auto_ack = False
    marker = None

    def __init__(self, connection_id=None, exchange=None, routing_key=None,
                 durable=None, exchange_type=None, exchange_durable=None,
                 exchange_auto_delete=None, exchange_auto_declare=None,
                 queue=None, queue_durable=None, queue_auto_delete=None,
                 queue_exclusive=None, queue_arguments=None,
                 queue_auto_declare=None, auto_declare=None, auto_delete=None,
                 auto_ack=None, marker=None):

        self._queue = None  # will default to self.queue

        # Allow class variables to provide defaults for:

        # connection_id
        if connection_id is not None:
            self.connection_id = connection_id
        assert self.connection_id is not None,\
            u"Consumer configuration is missing connection_id."

        # exchange
        if exchange is not None:
            self.exchange = exchange

        # routing_key
        if routing_key is not None:
            self.routing_key = routing_key

        # durable (and the default for exchange_durable)
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
        if self.queue is None and queue is None:
            queue = getattr(self, 'grokcore.component.directive.name', None)
        if queue is not None:
            self._queue = self.queue = queue
        assert self.queue is not None,\
            u"Consumer configuration is missing queue."
        # routing_key
        if self.routing_key is None:
            self.routing_key = self.queue
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

        # auto_ack
        if auto_ack is not None:
            self.auto_ack = auto_ack

        # marker
        if marker is not None:
            self.marker = marker

        # BBB for affinitic.zamqp
        if getattr(self, "messageInterface", None):
            from zope.deprecation import deprecated
            self.marker = self.messageInterface
            self.messageInterface =\
                deprecated(self.messageInterface,
                           ('Consumer.messageInterface is no more. '
                            'Please, use Consumer.marker instead.'))

    def consume(self, channel, tx_select, on_message_received):
        self._channel = channel
        self._tx_select = tx_select
        self._message_received_callback = on_message_received

        if self.exchange_auto_declare and self.exchange\
                and not self.exchange.startswith('amq.'):
            self.declare_exchange()
        elif self.queue_auto_declare and self.queue is not None\
                and not self.queue.startswith('amq.'):
            self.declare_queue()
        else:
            self.on_ready_to_consume()

    def declare_exchange(self):
        self._channel.exchange_declare(exchange=self.exchange,
                                       type=self.exchange_type,
                                       durable=self.exchange_durable,
                                       auto_delete=self.exchange_auto_delete,
                                       callback=self.on_exchange_declared)

    def on_exchange_declared(self, frame):
        logger.default(u"Consumer declared exchange '%s' on connection '%s'",
                       self.exchange, self.connection_id)
        if self.queue_auto_declare and self.queue is not None\
                and not self.queue.startswith('amq.'):
            self.declare_queue()
        else:
            self.on_ready_to_consume()

    def declare_queue(self):
        self._channel.queue_declare(queue=self.queue,
                                    durable=self.queue_durable,
                                    exclusive=self.queue_exclusive,
                                    auto_delete=self.queue_auto_delete,
                                    arguments=self.queue_arguments,
                                    callback=self.on_queue_declared)

    def on_queue_declared(self, frame):
        self._queue = frame.method.queue  # get the real queue name
        logger.default(u"Consumer declared queue '%s' on connection '%s'",
                       self._queue, self.connection_id)
        if self.auto_declare and self.exchange:
            self.bind_queue()
        else:
            self.on_ready_to_consume()

    def bind_queue(self):
        if type(self.routing_key) not in (tuple, list):
            self._channel.queue_bind(exchange=self.exchange, queue=self._queue,
                                     routing_key=self.routing_key,
                                     callback=self.on_queue_bound)
        else:
            self._channel.queue_bind(exchange=self.exchange, queue=self._queue,
                                     routing_key=self.routing_key[0],
                                     callback=self.on_queue_bound)

    def on_queue_bound(self, frame, index=0):
        logger.default(u"Consumer bound queue '%s' to exchange '%s' "
                       u"on connection '%s'",
                       self._queue, self.exchange, self.connection_id)
        if type(self.routing_key) not in (tuple, list):
            self.on_ready_to_consume()
        elif len(self.routing_key) <= index + 1:
            self.on_ready_to_consume()
        else:
            index = index + 1
            cb = lambda f, s=self, index=index: self.on_queue_bound(f, index)
            self._channel.queue_bind(exchange=self.exchange, queue=self._queue,
                                     routing_key=self.routing_key[index],
                                     callback=cb)

    def on_ready_to_consume(self):
        if self.marker is not None:  # False is allowed to trigger consuming
            logger.default(u"Consumer ready to consume queue '%s' on "
                           u"connection '%s'", self._queue, self.connection_id)
            self._channel.basic_consume(self.on_message_received,
                                        queue=self._queue)

    def on_message_received(self, channel, method_frame, header_frame, body):
        message = createObject('AMQPMessage',
                               body=body,
                               header_frame=header_frame,
                               method_frame=method_frame,
                               channel=self._channel,
                               tx_select=self._tx_select)
        if self.marker:
            alsoProvides(message, self.marker)

        if self.auto_ack:
            message.ack()  # immediate ack here (doesn't wait for transaction)

        self._message_received_callback(message)

    def __len__(self):
        """Return message count of the consumed queue"""
        with BlockingChannel(self.connection_id) as channel:
            frame = channel.queue_declare(queue=self._queue,
                                          durable=self.queue_durable,
                                          exclusive=self.queue_exclusive,
                                          auto_delete=self.queue_auto_delete,
                                          arguments=self.queue_arguments)
            return frame.method.message_count


class security_manager:

    def __init__(self, request, user_id):
        if user_id == 'Anonymous User':
            # Short circuit for 'Anonymous User' to avoid expensive lookups
            self.user = None
        else:
            self.request = request

            site = getSite()
            acl_users = site.get('acl_users')
            if acl_users:
                user = acl_users.getUser(user_id)

            if not user:
                root = site.getPhysicalRoot()
                acl_users = root.get('acl_users')
                if acl_users:
                    user = acl_users.getUser(user_id)
            if user:
                user = user.__of__(acl_users)

            self.user = user

    def __enter__(self):
        self.old_security_manager = getSecurityManager()
        if self.user:
            # Annotate transaction with the proper user
            txn = transaction.get()
            txn.setUser(str(self.user),
                        '/'.join(self.user.getPhysicalPath()[1:-1]))
            return newSecurityManager(self.request, self.user)
        else:
            return self.old_security_manager

    def __exit__(self, type, value, traceback):
        if self.user:
            setSecurityManager(self.old_security_manager)


class ConsumingView(BrowserView):
    """Consumes AMQP-messages send by consuming server.
    This view should be configured only for requests providing
    IConsumingRequests and not be available for regular requests.
    """

    implements(IPublishTraverse)

    def publishTraverse(self, request, name):
        """Allows arbitrary traverse to give more descriptive undo logs"""
        self.__name__ += '/%s' % name
        return self

    def __call__(self):
        message = self.request.environ.get('AMQP_MESSAGE')
        user_id = self.request.environ.get('AMQP_USER_ID')

        exchange = message.method_frame.exchange
        routing_key = message.method_frame.routing_key
        delivery_tag = message.method_frame.delivery_tag

        age = unicode(datetime.datetime.utcnow() - message.created_datetime)
        logger.default(u"Worker started processing message '%s' "
                       u"(status = '%s', age = '%s')",
                       delivery_tag, message.state, age)

        message._register()
        event = createObject('AMQPMessageArrivedEvent', message)

        with security_manager(self.request, user_id):
            try:
                notify(event)
            except ConflictError:
                logger.error(u"Conflict while working on message '%s' "
                             u"(status = '%s')",
                             delivery_tag, message.state)
                message.state = "ERROR"
                raise
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                err_handler = queryUtility(IErrorHandler, name=exchange)
                if err_handler is not None:
                    err_handler(message, exc_value, exc_traceback)
                else:
                    logger.error(u"Error while handling message '%s' sent to "
                                 u"exchange '%s' with routing key '%s'",
                                 delivery_tag, exchange, routing_key)
                    message.state = "ERROR"
                    raise

        age = unicode(datetime.datetime.utcnow() - message.created_datetime)
        if not (message.acknowledged or message.rejected):
            logger.warning(u"Nobody acknowledged or rejected message '%s' "
                           u"sent to exchange exchange '%s' "
                           u"with routing key '%s'",
                           delivery_tag, exchange, routing_key)
        else:
            logger.default(u"Letting Zope to commit database transaction for "
                           u"message '%s' (status = '%s', age = '%s')",
                           delivery_tag, message.state, age)

        return u''  # 200 No Content
