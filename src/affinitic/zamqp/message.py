# -*- coding: utf-8 -*-
"""
affinitic.zamqp

Licensed under the GPL license, see LICENCE.txt for more details.

Copyright by Affinitic sprl
Copyright by University of Jyväskylä
"""
import grokcore.component as grok

from zope.interface import implements, implementedBy
from zope.component import IFactory, queryUtility

from affinitic.zamqp.interfaces import IMessage, IMessageFactory, ISerializer
from affinitic.zamqp.transactionmanager import VTM


class Message(object, VTM):
    """
    A message that can be transaction aware
    """
    implements(IMessage)

    body = None
    header_frame = None
    method_frame = None
    channel = None

    state = None
    acknowledged = None

    def __init__(self, body=None, header_frame=None,
                 method_frame=None, channel=None):
        # de-serializer body when its content_type is supported
        content_type = getattr(header_frame, "content_type", None)
        util = queryUtility(ISerializer, name=content_type)
        if util:
            self.body = util.serialize(body)
        else:
            self.body = body

        self.header_frame = header_frame
        self.method_frame = method_frame
        self.channel = channel
        self.state = 'RECEIVED'
        self.acknowledged = False

    def ack(self):
        """
        Mark the message as acknowledge.

        If the message is registered in a transaction, we defer transmition of
        acknowledgement.

        If the message is not registered in a transaction, we transmit
        acknowledgement immediately.
        """
        if not self.acknowledged and not self.registered():
            if self.channel:
                self.channel.basic_ack(
                    delivery_tag=self.method_frame.delivery_tag)
            self.state = 'ACK'
        self.acknowledged = True

    def _abort(self):
        self.state = 'RECEIVED'
        self.acknowledged = False

    def _finish(self):
        if self.acknowledged and not self.state == 'ACK':
            if self.channel:
                self.channel.basic_ack(
                    delivery_tag=self.method_frame.delivery_tag)
            self.state = 'ACK'

    def __getattr__(self, name):
        if hasattr(self.__class__, name):
            return object.__getattribute__(self, name)
        else:
            return getattr(self.body, name)

    def sortKey(self, *ignored):
        return '~zamqp 9'  # always be the last one!


class MessageFactory(object):
    grok.implements(IMessageFactory)

    title = u'Message Factory'
    description = u'Help creating a new message'

    def getInterfaces(self):
        return implementedBy(Message)

    def __call__(self, body=None, header_frame=None,
                 method_frame=None, channel=None):
        return Message(body=body, header_frame=header_frame,
                       method_frame=method_frame, channel=channel)

grok.global_utility(MessageFactory, provides=IFactory, name='AMQPMessage')
