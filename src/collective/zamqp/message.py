# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyright (c) 2012 University of Jyväskylä and Contributors.
###
# This module is a derivate of affinitic.zamqp.message.
#
# Copyright by Affinitic sprl
###
"""Transaction aware AMQP message wrapper"""

import sys
import datetime

import grokcore.component as grok

from ZODB.POSException import ConflictError

from zope.interface import implements, implementedBy
from zope.component import IFactory, queryUtility
from zope.component.interfaces import ObjectEvent

from collective.zamqp.utils import logger
from collective.zamqp.interfaces import\
    IMessage, IMessageArrivedEvent, ISerializer
from collective.zamqp.transactionmanager import VTM

_EMPTY_MARKER = object()


class Message(object, VTM):
    """A message that can be transaction aware"""

    implements(IMessage)

    created_datetime = None

    header_frame = None
    method_frame = None
    channel = None
    tx_select = False

    state = None  # 'RECEIVED' is received and may be partially handled
                  # 'ACK' is received, handled and acknowledged
                  # 'REJECTED' is rejected without requeuing
                  # 'REQUEUED' is requeued, e.g. because of ConflictError
                  # 'ERROR' is received, but consuming has ended with error;
                  #         transaction-aware messages will transit to 'FAILED'
                  # 'FAILED' consuming has ended with any failure;
                  #          message is left unacknowledged
    acknowledged = None
    rejected = None
    requeued = None

    _serialized_body = None
    _deserialized_body = None

    def __init__(self, body=None, header_frame=None,
                 method_frame=None, channel=None, tx_select=None):

        self.created_datetime = datetime.datetime.utcnow()

        self._serialized_body = body
        self._deserialized_body = _EMPTY_MARKER

        self.header_frame = header_frame
        self.method_frame = method_frame
        self.channel = channel

        if tx_select is not None:
            self.tx_select = tx_select

        self.state = 'RECEIVED'
        self.acknowledged = False

    @property
    def body(self):
        if self._deserialized_body is _EMPTY_MARKER:
            # Read content_type from message:
            content_type = getattr(self.header_frame, 'content_type', None)
            # XXX: Sometimes must go deeper to find the content_type
            if content_type is None:
                content_type = (
                    getattr(self.header_frame, 'headers', None) or {}
                ).get('properties', {}).get('content_type')
            # De-serializer body when its content_type is supported:
            if content_type:
                util = queryUtility(ISerializer, name=content_type)
                if util:
                    self._deserialized_body =\
                        util.deserialize(self._serialized_body)

        if self._deserialized_body is not _EMPTY_MARKER:
            return self._deserialized_body
        else:
            return self._serialized_body

    def ack(self):
        """Mark the message as acknowledged.

        If the message is registered in a transaction, we defer the
        transmission of acknowledgement.

        If the message is not registered in a transaction, we transmit
        acknowledgement immediately."""

        if not self.acknowledged and not self.registered():
            self._ack()
        self.acknowledged = True

    def reject(self, requeue=True):
        """Mark the message as rejected.

        If the message is registered in a transaction, we defer the
        transmission of rejection.

        If the message is not registered in a transaction, we transmit
        rejection immediately."""

        if not self.rejected and not self.registered():
            self._reject(requeue)
        self.rejected = True
        self.requeued = requeue

    def _ack(self):
        self.acknowledged = True
        if self.channel:
            self.channel.basic_ack(
                delivery_tag=self.method_frame.delivery_tag)
            self.state = 'ACK'

        if self.channel and self.tx_select:
            self.channel.tx_commit()  # min support for transactional channel

        age = unicode(datetime.datetime.utcnow() - self.created_datetime)
        logger.default(u"Handled message '%s' (status = '%s', age = '%s')",
                       self.method_frame.delivery_tag, self.state, age)

    def _reject(self, requeue=True):
        self.rejected = True
        self.requeued = requeue
        if self.channel:
            self.channel.basic_reject(
                delivery_tag=self.method_frame.delivery_tag, requeue=requeue)
            if requeue:
                self.state = 'REQUEUED'
            else:
                self.state = 'REJECTED'

        if self.channel and self.tx_select:
            self.channel.tx_commit()  # min support for transactional channel

        age = unicode(datetime.datetime.utcnow() - self.created_datetime)
        logger.default(u"Rejected message '%s' (status = '%s', age = '%s')",
                       self.method_frame.delivery_tag, self.state, age)

    def _abort(self):
        # collect execution info for guessing the reason for abort
        exc_type, exc_value, exc_traceback = sys.exc_info()

        if self.state != 'ACK':
            self.acknowledged = False
        if self.state == 'ACK' and issubclass(exc_type, ConflictError):
            if not getattr(self, '_aborted', False):
                logger.warning(
                    u"Transaction aborted due to database conflict. "
                    u"Message '%s' was acked before commit and could "
                    u"not be requeued (status = '%s')",
                    self.method_frame.delivery_tag, self.state)
                self._aborted = True
        elif self.state not in ('FAILED', 'REQUEUED'):
            # on transactional channel, rollback on abort
            if self.channel and self.tx_select:
                self.channel.tx_rollback()  # min support for transactional
                                            # channel
                # ^ XXX: Because the same channel may be shared by multiple
                # threads, tx_rollback may be far from safe. It's supported
                # only to make single-threaded AMQP-consuming ZEO-clients
                # support transactional channel. DO NOT run multi-threaded
                # consuming-server with transactional channel.

            # reject messages with requeue when ConflictError in ZPublisher
            if self.state != 'ERROR' and issubclass(exc_type, ConflictError):
                # reject message with requeue
                self.channel.basic_reject(
                    delivery_tag=self.method_frame.delivery_tag, requeue=True)
                self.state = "REQUEUED"

                logger.default(
                    u"Transaction aborted due to database conflict. "
                    u"Requeued message '%s' (status = '%s')",
                    self.method_frame.delivery_tag, self.state)
            # otherwise, message handling has failed and un-acknowledged
            else:
                self.state = 'FAILED'

    def _finish(self):
        if self.acknowledged and not self.state == 'ACK':
            self._ack()
        if self.rejected:
            if self.state == 'ACK':
                logger.warning(
                    u"Message '%s' was both acknowledged and rejected "
                    u"(status = '%s'). Rejection was cancelled and "
                    u"message was acknowledged",
                    self.method_frame.delivery_tag, self.state)
            elif self.state not in ['REJECTED', 'REQUEUED']:
                self._reject(self.requeued)

    def sortKey(self, *ignored):
        return '~zamqp 9'  # always be the last one!


class MessageFactory(object):
    grok.implements(IFactory)

    title = u'Message Factory'
    description = u'Help creating a new message'

    def getInterfaces(self):
        return implementedBy(Message)

    def __call__(self, body=None, header_frame=None,
                 method_frame=None, channel=None, tx_select=None):
        return Message(body=body, header_frame=header_frame,
                       method_frame=method_frame, channel=channel,
                       tx_select=tx_select)

grok.global_utility(MessageFactory, provides=IFactory, name='AMQPMessage')


class MessageArrivedEvent(ObjectEvent):
    """A message has been received"""

    implements(IMessageArrivedEvent)


class MessageArrivedEventFactory(object):
    grok.implements(IFactory)

    title = u'Message Arrived Event Factory'
    description = u'Help creating a new message arrived event'

    def getInterfaces(self):
        return implementedBy(MessageArrivedEvent)

    def __call__(self, message=None):
        return MessageArrivedEvent(message)

grok.global_utility(MessageArrivedEventFactory, provides=IFactory,
                    name='AMQPMessageArrivedEvent')
