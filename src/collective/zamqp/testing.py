# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyrighted by University of Jyväskylä and Contributors.
###
"""Test fixtures"""

import asyncore

from zope.configuration import xmlconfig

from plone.testing import Layer, z2

from rabbitfixture.server import (
    RabbitServer,
    RabbitServerResources
)


def runAsyncTest(testMethod, timeout=100, loop_timeout=0.1, loop_count=1):
    """ Helper method for running tests requiring asyncore loop """
    while True:
        try:
            asyncore.loop(timeout=loop_timeout, count=loop_count)
            return testMethod()
        except AssertionError:
            if timeout > 0:
                timeout -= 1
                continue
            else:
                raise


class FixedHostname(RabbitServerResources):
    """Allocate resources for RabbitMQ server with the explicitly defined
    hostname. (Does not query the hostname from a socket as the default
    implementation does.) """

    @property
    def fq_nodename(self):
        """The node of the RabbitMQ that is being exported."""
        return '%s@%s' % (self.nodename, self.hostname)


class Rabbit(Layer):

    def setUp(self):
        # setup a RabbitMQ
        config = FixedHostname()
        self['rabbit'] = RabbitServer(config=config)
        self['rabbit'].setUp()
        # define a shortcut to rabbitmqctl
        self['rabbitctl'] = self['rabbit'].runner.environment.rabbitctl

    def testTearDown(self):
        self['rabbitctl']('stop_app')
        self['rabbitctl']('reset')
        self['rabbitctl']('start_app')

    def tearDown(self):
        try:
            self['rabbit'].cleanUp()
        except OSError as e:
            if e.errno == 3:  # [Errno 3] No such process
                # Rabbit may have already died because of KeyboardInterrupt
                pass
            else:
                raise

RABBIT_FIXTURE = Rabbit()

RABBIT_APP_INTEGRATION_TESTING = z2.IntegrationTesting(
    bases=(RABBIT_FIXTURE, z2.STARTUP), name='RabbitAppFixture:Integration')
RABBIT_APP_FUNCTIONAL_TESTING = z2.FunctionalTesting(
    bases=(RABBIT_FIXTURE, z2.STARTUP), name='RabbitAppFixture:Functional')


class Testing(Layer):
    defaultBases = (RABBIT_FIXTURE, z2.STARTUP)

    def setUp(self):
        import collective.zamqp
        xmlconfig.file('testing.zcml', collective.zamqp,
                       context=self['configurationContext'])

TESTING_FIXTURE = Testing()


class ZAMQP(Layer):
    defaultBases = (RABBIT_FIXTURE, z2.STARTUP)

    def __init__(self, user_id='Anonymous User',
                 zserver=False, trace_on=False):
        super(ZAMQP, self).__init__()
        self.zserver = zserver
        self.trace_on = trace_on
        self.user_id = user_id

    def setUp(self):

        # Enable trace
        if self.trace_on:
            self['rabbitctl']('trace_on')

        # Define dummy request handler to replace ZPublisher

        def handler(app, request, response):
            from zope.event import notify
            from zope.component import createObject
            message = request.environ.get('AMQP_MESSAGE')
            event = createObject('AMQPMessageArrivedEvent', message)
            notify(event)

        # Define ZPublisher-based request handler to be used with zserver

        def zserver_handler(app, request, response):
            from ZPublisher import publish_module
            publish_module(app, request=request, response=response)

        # Create connections and consuming servers for registered
        # producers and consumers

        from zope.interface import Interface
        from zope.component import getSiteManager
        from collective.zamqp.interfaces import (
            IBrokerConnection,
            IProducer,
            IConsumer,
            IMessageArrivedEvent
        )
        from collective.zamqp.connection import BrokerConnection
        from collective.zamqp.server import ConsumingServer
        from collective.zamqp.producer import Producer
        from collective.zamqp.consumer import Consumer

        sm = getSiteManager()

        connections = []
        consuming_servers = []

        for producer in sm.getAllUtilitiesRegisteredFor(IProducer):
            if not producer.connection_id in connections:
                connection = BrokerConnection(producer.connection_id,
                                              port=self['rabbit'].config.port)
                sm.registerUtility(connection, provided=IBrokerConnection,
                                   name=connection.connection_id)
                connections.append(connection.connection_id)

                # generate default producer with the name of the connection
                producer = Producer(connection.connection_id, exchange="",
                                    routing_key="", durable=False,
                                    auto_declare=False)
                sm.registerUtility(producer, provided=IProducer,
                                   name=connection.connection_id)

        # Register Firehose
        if self.trace_on:
            class IFirehoseMessage(Interface):
                """Marker interface for firehose message"""

            def handleFirehoseMessage(message, event):
                print message.method_frame
                print message.header_frame
                print message.body
                message.ack()

            consumer = Consumer("amq.rabbitmq.trace",
                                exchange="amq.rabbitmq.trace",
                                queue="", routing_key="#", durable=False,
                                auto_declare=True, marker=IFirehoseMessage)

            sm.registerUtility(consumer, provided=IConsumer,
                               name="amq.rabbitmq.trace")

            sm.registerHandler(
                handleFirehoseMessage,
                (IFirehoseMessage, IMessageArrivedEvent))

        for consumer in sm.getAllUtilitiesRegisteredFor(IConsumer):
            if not consumer.connection_id in connections:
                connection = BrokerConnection(consumer.connection_id,
                                              port=self['rabbit'].config.port)
                sm.registerUtility(connection, provided=IBrokerConnection,
                                   name=connection.connection_id)
                connections.append(connection.connection_id)

                # generate default producer with the name of the connection
                producer = Producer(connection.connection_id, exchange="",
                                    routing_key="", durable=False,
                                    auto_declare=False)
                sm.registerUtility(producer, provided=IProducer,
                                   name=connection.connection_id)

            if not consumer.connection_id in consuming_servers:
                if self.zserver:
                    ConsumingServer(consumer.connection_id, 'plone',
                                    user_id=self.user_id,
                                    handler=zserver_handler,
                                    hostname='nohost',  # taken from z2.Startup
                                    port=80,
                                    use_vhm=False)
                else:
                    ConsumingServer(consumer.connection_id, 'plone',
                                    user_id=self.user_id,
                                    handler=handler,
                                    use_vhm=False)
                consuming_servers.append(consumer.connection_id)

        # Connect all connections

        from collective.zamqp import connection
        connection.connect_all()

    def testSetUp(self):
        # Re-enable trace
        if self.trace_on:
            self['rabbitctl']('trace_on')

    def testTearDown(self):
        # Disable trace
        if self.trace_on:
            self['rabbitctl']('trace_off')

    # def testTearDown(self):
    #     from zope.component import getUtilitiesFor
    #     from collective.zamqp.interfaces import IBrokerConnection
    #     for connection_id, connection in getUtilitiesFor(IBrokerConnection):
    #         if connection.is_open:
    #             connection._channel.close()

ZAMQP_FIXTURE = ZAMQP()
ZAMQP_ADMIN_FIXTURE = ZAMQP(user_id='admin')

ZAMQP_DEBUG_FIXTURE = ZAMQP(trace_on=True)
ZAMQP_ADMIN_DEBUG_FIXTURE = ZAMQP(user_id='admin', trace_on=True)

ZAMQP_ZSERVER_FIXTURE = ZAMQP(zserver=True)
ZAMQP_ZSERVER_ADMIN_FIXTURE = ZAMQP(user_id='admin', zserver=True)

ZAMQP_ZSERVER_DEBUG_FIXTURE = ZAMQP(zserver=True, trace_on=True)
ZAMQP_ZSERVER_ADMIN_DEBUG_FIXTURE = ZAMQP(user_id='admin',
                                          zserver=True, trace_on=True)

ZAMQP_INTEGRATION_TESTING = z2.IntegrationTesting(
    bases=(TESTING_FIXTURE, ZAMQP_FIXTURE),
    name='ZAMQP:Integration')

ZAMQP_FUNCTIONAL_TESTING = z2.FunctionalTesting(
    bases=(TESTING_FIXTURE, ZAMQP_FIXTURE),
    name='ZAMQP:Functional')
