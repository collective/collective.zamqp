# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyright (c) 2012 University of Jyväskylä and Contributors.
###
"""ZConfig datatype support for AMQP Consuming Server"""

import asyncore
import Lifetime


class BrokerConnectionFactory(object):

    def __init__(self, section):
        self.connection_id = section.connection_id

        self.hostname = section.hostname
        self.port = section.port
        self.virtual_host = section.virtual_host

        self.username = section.username
        self.password = section.password

        self.heartbeat = section.heartbeat

        self.prefetch_count = section.prefetch_count
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
                                      prefetch_count=self.prefetch_count,
                                      tx_select=self.tx_select)

        # set expected ZServer-properties to support debugtoolbar
        connection.server_name = "ZAMQP Broker Connection"
        connection.ip = None

        provideUtility(connection, IBrokerConnection, name=self.connection_id)

        if self.keepalive:
            from collective.zamqp.utils import logger
            logger.default(u"Setting up keepalive (%s s) for connection '%s'",
                           self.keepalive, self.connection_id)

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

        # set expected ZServer-properties to support debugtoolbar
        connection.server_name = "ZAMQP Broker Connection"
        connection.ip = None

        return connection


def lifetime_loop():
    # The main loop. Stay in here until we need to shutdown
    map = asyncore.socket_map
    timeout = 1.0
    while map and Lifetime._shutdown_phase == 0:
        asyncore.poll(timeout, map)


class ConsumingServerFactory(object):

    def __init__(self, section):
        self.connection_id = section.connection_id
        self.site_id = section.site_id
        self.user_id = section.user_id or 'Anonymous User'
        self.hostname = section.hostname
        self.port = section.port
        self.scheme = section.scheme
        self.use_vhm = section.use_vhm
        self.vhm_method_prefix = section.vhm_method_prefix

        # Just in case, mimic ZServer.datatypes.ServerFactory
        self.ip = None

        if section.override_lifetime_loop:
            Lifetime.lifetime_loop = lifetime_loop  # override lifetime_loop

    def prepare(self, defaulthost='', dnsresolver=None,
                module=None, env=None, portbase=None):
        return

    def servertype(self):
        return "AMQP Consuming Server"

    def create(self):
        from collective.zamqp.server import ConsumingServer
        from ZServer.AccessLogger import access_logger

        server = ConsumingServer(self.connection_id,
                                 self.site_id,
                                 self.user_id,
                                 self.scheme,
                                 self.hostname,
                                 self.port,
                                 self.use_vhm,
                                 self.vhm_method_prefix,
                                 access_logger)

        # set expected ZServer-properties to support debugtoolbar
        server.server_name = "ZAMQP Consuming Server"
        server.ip = None

        return server
