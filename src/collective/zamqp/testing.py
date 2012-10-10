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


class ZAMQP(Layer):
    defaultBases = (RABBIT_FIXTURE, z2.STARTUP)

    def setUp(self):
        import collective.zamqp
        xmlconfig.file('testing.zcml', collective.zamqp,
                       context=self['configurationContext'])

        # Set AMQP port from the RabbitFixture
        from zope.component import getUtility
        from collective.zamqp.interfaces import IBrokerConnection
        connection = getUtility(IBrokerConnection, name='test.connection')
        connection.port = self['rabbit'].config.port

        # Define dummy request handler to replace ZPublisher
        def handler(app, request, response):
            from zope.event import notify
            from zope.component import createObject
            message = request.environ.get('AMQP_MESSAGE')
            event = createObject('AMQPMessageArrivedEvent', message)
            notify(event)

        # Register consuming server
        from collective.zamqp.server import ConsumingServer
        self['zamqp'] = ConsumingServer(connection.connection_id, 'plone',
                                        handler=handler)

ZAMQP_FIXTURE = ZAMQP()


class ZAMQPConnectAll(Layer):
    defaultBases = ()

    def setUp(self):
        # Init connections
        from collective.zamqp import connection
        connection.connect_all()


ZAMQP_CONNECT_ALL_FIXTURE = ZAMQPConnectAll()


ZAMQP_INTEGRATION_TESTING = z2.IntegrationTesting(
    bases=(ZAMQP_FIXTURE, ZAMQP_CONNECT_ALL_FIXTURE),
    name='ZAMQP:Integration')
ZAMQP_FUNCTIONAL_TESTING = z2.FunctionalTesting(
    bases=(ZAMQP_FIXTURE, ZAMQP_CONNECT_ALL_FIXTURE),
    name='ZAMQP:Functional')
