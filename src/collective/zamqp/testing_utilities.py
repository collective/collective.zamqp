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
from collective.zamqp.producer import Producer
from collective.zamqp.consumer import Consumer

import logging
from testfixtures import log_capture


class IMessage(Interface):
    """Message marker interface"""


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


class IPickleMessage(Interface):
    """Message marker interface"""


class PickleProducer(Producer):
    grok.name("my.picklequeue")

    connection_id = "test.connection"
    queue = "my.picklequeue"

    serializer = "application/x-python-serialize"


class PickleConsumer(Consumer):
    grok.name("my.picklequeue")

    connection_id = "test.connection"
    queue = "my.picklequeue"

    marker = IPickleMessage


@log_capture()
@grok.subscribe(IPickleMessage, IMessageArrivedEvent)
def receivedPickleMessage(message, event):
    logger = logging.getLogger("c.zamqp.tests")
    logger.info(str(message.header_frame))
    logger.info(message.body)
    logger.info(type(message.body))
    message.ack()
