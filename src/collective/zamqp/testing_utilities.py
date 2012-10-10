# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyrighted by University of Jyväskylä and Contributors.
###
"""Test utilities"""

from grokcore import component as grok

from zope.interface import Interface

from collective.zamqp.interfaces import IMessageArrivedEvent
from collective.zamqp.connection import BrokerConnection
from collective.zamqp.producer import Producer
from collective.zamqp.consumer import Consumer


class IMessage(Interface):
    """Message marker interface"""


class TestConnection(BrokerConnection):
    grok.name("test.connection")


class SimpleProducer(Producer):
    grok.name("my.queue")

    connection_id = "test.connection"
    queue = "my.queue"

    serializer = "text/plain"


class SimpleConsumer(Consumer):
    grok.name("my.queue")

    connection_id = "test.connection"
    queue = "my.queue"

    marker = IMessage


@grok.subscribe(IMessage, IMessageArrivedEvent)
def received(message, event):
    message.ack()
