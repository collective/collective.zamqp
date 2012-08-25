# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyright (c) 2012 University of Jyväskylä and Contributors.
###
"""ZConfig datatype support for AMQP Consuming Server"""


class BrokerConnectionFactory(object):

    def __init__(self, section):
        self.connection_id = section.connection_id

        self.hostname = section.hostname
        self.port = section.port
        self.virtual_host = section.virtual_host

        self.username = section.username
        self.password = section.password

        self.heartbeat = section.heartbeat
        self.tx_select = section.tx_select

        # generate ping-keepalive until heartbeat really works
        self.keepalive = section.keepalive

        # generate default producer with the name of the connection
        self.producer = section.producer

        # just in case, mimic ZServer.datatypes.ServerFactory
        self.ip = self.host = None

    def prepare(self, defaulthost='', dnsresolver=None,
                module=None, env=None, portbase=None):
        return

    def servertype(self):
        return "AMQP Broker Connection"

    def create(self):
        from zope.component import provideUtility

        from collective.zamqp.interfaces import IBrokerConnection
        from collective.zamqp.connection import BrokerConnection

        connection = BrokerConnection(connection_id=self.connection_id,
                                      hostname=self.hostname,
                                      port=self.port,
                                      virtual_host=self.virtual_host,
                                      username=self.username,
                                      password=self.password,
                                      heartbeat=self.heartbeat,
                                      tx_select=self.tx_select)

        provideUtility(connection, IBrokerConnection, name=self.connection_id)

        if self.keepalive:
            # register a ping producer, a ping consumer, a ping view and a ping
            # clock-server to keep the connection alive

            from collective.zamqp.interfaces import IProducer, IConsumer
            from collective.zamqp import keepalive

            name = "%s.ping" % self.connection_id

            # the producer
            producer = keepalive.PingProducer(self.connection_id)
            provideUtility(producer, IProducer, name=name)

            # the consumer
            consumer = keepalive.PingConsumer(self.connection_id)
            provideUtility(consumer, IConsumer, name=name)

            from zope.interface import Interface
            from zope.component import provideAdapter

            from OFS.interfaces import IApplication

            # the view
            ping = lambda context, request: lambda: keepalive.ping(name)
            provideAdapter(ping, adapts=(IApplication, Interface),
                           provides=Interface, name=name)

            # the clock-server
            from ZServer.AccessLogger import access_logger
            from ZServer.ClockServer import ClockServer
            clock = ClockServer(method="/%s" % name, period=self.keepalive,
                                host="localhost", logger=access_logger)

            # just in case, store the created utilities, view and server
            connection._keepalive = {"producer": producer,
                                     "consumer": consumer,
                                     "view": ping,
                                     "clock": clock}

        if self.producer:
            # generate default producer with the name of the connection
            from collective.zamqp.interfaces import IProducer
            from collective.zamqp.producer import Producer

            producer = Producer(self.connection_id, exchange="",
                                routing_key="", durable=False,
                                auto_declare=False)
            provideUtility(producer, IProducer, name=self.connection_id)

        return connection


class ConsumingServerFactory(object):

    def __init__(self, section):
        self.connection_id = section.connection_id
        self.site_id = section.site_id
        self.user_id = section.user_id or 'Anonymous User'

        # Just in case, mimic ZServer.datatypes.ServerFactory
        self.ip = self.host = self.port = None

    def prepare(self, defaulthost='', dnsresolver=None,
                module=None, env=None, portbase=None):
        return

    def servertype(self):
        return "AMQP Consuming Server"

    def create(self):
        from collective.zamqp.server import ConsumingServer
        from ZServer.AccessLogger import access_logger

        return ConsumingServer(self.connection_id,
                               self.site_id,
                               self.user_id,
                               access_logger)
