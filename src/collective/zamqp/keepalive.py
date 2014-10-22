# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyright (c) 2012 University of Jyväskylä and Contributors.
###
"""
Base classes for registering ping to keep the connection alive in environments,
where firewalls close idle connections. In addition, ping causes enough socket
traffic (for asyncore) to help re-connections on otherwise silent
AMQP-dedicated zeo-clients.

Usage
-----

1. Define producer and consumer::

    from collective.zamqp.keepalive import PingProducer, PingConsumer

    class Ping(PingProducer):
        grok.name("myapp.ping")
        connection_id = "myapp.amqp"

    class Pong(PingConsumer):
        grok.name("myapp.pong")
        connection_id = "myapp.amqp"

2. Define view to send ping message::

    from Products.CMFPlone.interfaces import IPloneSiteRoot

    from collective.zamqp.keepalive import ping

    class PingView(grok.View):
        grok.name("myapp.ping")
        grok.context(IPloneSiteRoot)
        grok.require("zope.Public")

        render = lambda self: ping("myapp.ping")

3. Define Zope clock-server to call the view once per a minute::

    <clock-server>
        method /mysite/@@my-app-ping
        period 60
        host localhost
    </clock-server>
"""

from grokcore import component as grok

from zope.component import getUtility

from collective.zamqp.utils import logger
from collective.zamqp.producer import Producer
from collective.zamqp.consumer import Consumer
from collective.zamqp.interfaces import IProducer


class PingProducer(Producer):
    """An example ping-message producer base class, which:

    1) declares transient *direct* exchange *collective.zamqp*
    2) declares transient queue *collective.zamqp.connection_id*
    3) bind queue to exchange by its name."""

    grok.baseclass()

    exchange = 'collective.zamqp'

    @property
    def routing_key(self):
        return self.queue

    @property
    def queue(self):
        return 'collective.zamqp.%s' % self.connection_id

    queue_arguments = {
        'x-message-ttl': 3600000,  # 60 * 60s = 1 minute
    }

    serializer = 'text/plain'
    durable = False


class PingConsumer(Consumer):
    """An example ping-consumer base class, which:

    1) declares transient queue *collective.zamqp.connection_id*
    2) consumes and acks all ping-messages with minimal effort."""

    grok.baseclass()

    @property
    def queue(self):
        return 'collective.zamqp.%s' % self.connection_id

    queue_arguments = {
        'x-message-ttl': 3600000,  # 60 * 60s = 1 minute
    }

    durable = False
    marker = False  # allows consuming, but wouldn't stamp messages

    def on_message_received(self, channel, method_frame, header_frame, body):
        channel.basic_ack(delivery_tag=method_frame.delivery_tag)
        if self._tx_select:
            channel.tx_commit()  # min support for transactional channel
        logger.debug('....PONG')


def ping(name):
    producer = getUtility(IProducer, name=name)
    producer._register()
    producer.publish('PING')
    logger.debug('PING....')
