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


def runAsyncTest(testMethod, timeout=100):
    """ Helper method for running tests requiring asyncore loop """
    try:
        asyncore.loop(timeout=0.1, count=1)
        return testMethod()
    except AssertionError:
        if timeout > 0:
            return runAsyncTest(testMethod, timeout - 1)
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

    def tearDown(self):
        self['rabbit'].cleanUp()

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

    def setUp(self):

        # Define dummy request handler to replace ZPublisher

        def handler(app, request, response):
            from zope.event import notify
            from zope.component import createObject
            message = request.environ.get('AMQP_MESSAGE')
            event = createObject('AMQPMessageArrivedEvent', message)
            notify(event)

        # Create connections and consuming servers for registered
        # producers and consumers

        from zope.component import getSiteManager
        from collective.zamqp.interfaces import (
            IBrokerConnection,
            IProducer,
            IConsumer
        )
        from collective.zamqp.connection import BrokerConnection
        from collective.zamqp.server import ConsumingServer

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

        for consumer in sm.getAllUtilitiesRegisteredFor(IConsumer):
            if not consumer.connection_id in connections:
                connection = BrokerConnection(producer.connection_id,
                                              port=self['rabbit'].config.port)
                sm.registerUtility(connection, provided=IBrokerConnection,
                                   name=connection.connection_id)
                connections.append(connection.connection_id)

            if not consumer.connection_id in consuming_servers:
                ConsumingServer(consumer.connection_id, 'plone',
                                handler=handler)
                consuming_servers.append(connection.connection_id)

        # Connect all connections

        from collective.zamqp import connection
        connection.connect_all()


ZAMQP_FIXTURE = ZAMQP()


ZAMQP_INTEGRATION_TESTING = z2.IntegrationTesting(
    bases=(TESTING_FIXTURE, ZAMQP_FIXTURE),
    name='ZAMQP:Integration')
ZAMQP_FUNCTIONAL_TESTING = z2.FunctionalTesting(
    bases=(TESTING_FIXTURE, ZAMQP_FIXTURE),
    name='ZAMQP:Functional')
