# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyrighted by University of Jyväskylä and Contributors.
###
"""Test fixtures"""

from collective.zamqp.connection import BrokerConnection
from collective.zamqp.consumer import Consumer
from collective.zamqp.interfaces import IBrokerConnection
from collective.zamqp.interfaces import IConsumer
from collective.zamqp.interfaces import IMessageArrivedEvent
from collective.zamqp.interfaces import IProducer
from collective.zamqp.producer import Producer
from collective.zamqp.server import ConsumingServer
from plone.testing import Layer
from plone.testing import z2
from plone.testing import zca
from rabbitfixture.server import RabbitServer
from rabbitfixture.server import RabbitServerResources
from tempfile import mktemp
from zope.component import createObject
from zope.component import getSiteManager
from zope.configuration import xmlconfig
from zope.event import notify
from zope.interface import Interface
from ZPublisher import publish_module
import asyncore
import collective.zamqp
import collective.zamqp.connection
import os


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

        # rabbitfixture does not set enabled plugins file
        self['enabled_plugins'] = mktemp()
        with open(self['enabled_plugins'], 'w') as fp:
            fp.write('[].')
        self['RABBITMQ_ENABLED_PLUGINS_FILE'] = os.environ.get(
            'RABBITMQ_ENABLED_PLUGINS_FILE')
        os.environ['RABBITMQ_ENABLED_PLUGINS_FILE'] = self['enabled_plugins']

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

        # rabbitfixture does not set enabled plugins file
        if self['RABBITMQ_ENABLED_PLUGINS_FILE'] is None:
            os.environ.pop('RABBITMQ_ENABLED_PLUGINS_FILE')
        else:
            os.environ['RABBITMQ_ENABLED_PLUGINS_FILE'] = \
                self['RABBITMQ_ENABLED_PLUGINS_FILE']
        os.unlink(self['enabled_plugins'])

RABBIT_FIXTURE = Rabbit()

RABBIT_APP_INTEGRATION_TESTING = z2.IntegrationTesting(
    bases=(RABBIT_FIXTURE, z2.STARTUP), name='RabbitAppFixture:Integration')
RABBIT_APP_FUNCTIONAL_TESTING = z2.FunctionalTesting(
    bases=(RABBIT_FIXTURE, z2.STARTUP), name='RabbitAppFixture:Functional')


class ZAMQP(Layer):
    defaultBases = (RABBIT_FIXTURE, z2.STARTUP)

    def __init__(self, user_id='Anonymous User',
                 zserver=False, trace_on=False):
        super(ZAMQP, self).__init__()
        self.zserver = zserver
        self.trace_on = trace_on
        self.user_id = user_id

        # Registered utilities and handlers are storedin setUp to be explicitly
        # unregistered during tearDown.
        self.utilities = []
        self.handlers = []

    def setUp(self):
        # Enable trace
        if self.trace_on:
            self['rabbitctl']('trace_on')

        # Define dummy request handler to replace ZPublisher

        def handler(app, request, response):
            message = request.environ.get('AMQP_MESSAGE')
            event = createObject('AMQPMessageArrivedEvent', message)
            notify(event)

        # Define ZPublisher-based request handler to be used with zserver

        def zserver_handler(app, request, response):
            publish_module(app, request=request, response=response)

        # Create connections and consuming servers for registered
        # producers and consumers

        connections = []
        consuming_servers = []

        sm = getSiteManager()

        for producer in sm.getAllUtilitiesRegisteredFor(IProducer):
            if not producer.connection_id in connections:
                connection = BrokerConnection(producer.connection_id,
                                              port=self['rabbit'].config.port)
                sm.registerUtility(connection, provided=IBrokerConnection,
                                   name=connection.connection_id)
                connections.append(connection.connection_id)
                self.utilities.append(connection)

                # generate default producer with the name of the connection
                producer = Producer(connection.connection_id, exchange="",
                                    routing_key="", durable=False,
                                    auto_declare=False)
                sm.registerUtility(producer, provided=IProducer,
                                   name=connection.connection_id)
                self.utilities.append(producer)

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
            self.utilities.append(consumer)

            registerHandler(handleFirehoseMessage,
                           (IFirehoseMessage, IMessageArrivedEvent))
            self.handlers.append(handleFireHoseMessage)

        for consumer in sm.getAllUtilitiesRegisteredFor(IConsumer):
            if not consumer.connection_id in connections:
                connection = BrokerConnection(consumer.connection_id,
                                              port=self['rabbit'].config.port)
                sm.registerUtility(connection, provided=IBrokerConnection,
                                   name=connection.connection_id)
                connections.append(connection.connection_id)
                self.utilities.append(connection)

                # generate default producer with the name of the connection
                producer = Producer(connection.connection_id, exchange="",
                                    routing_key="", durable=False,
                                    auto_declare=False)
                sm.registerUtility(producer, provided=IProducer,
                                   name=connection.connection_id)
                self.utilities.append(producer)

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
        collective.zamqp.connection.connect_all()

    def testSetUp(self):
        # Re-enable trace
        if self.trace_on:
            self['rabbitctl']('trace_on')

    def testTearDown(self):
        # Disable trace
        if self.trace_on:
            self['rabbitctl']('trace_off')

    def tearDown(self):
        sm = getSiteManager()
        for utility in self.utilities:
            # XXX: Removing connection from ZCA is not enough, because they are
            # bound to asyncore loop and reconnect on disconnect. Therefore we
            # apply magic, to disable reconnection.
            if isinstance(utility, BrokerConnection):
                utility._reconnection_timeout = True
        while self.utilities:
            sm.unregisterUtility(self.utilities.pop())
        while self.handlers:
            sm.unregisterHandler(self.handlers.pop())



# Generic ZAMQP test fixture

ZAMQP_FIXTURE = ZAMQP()
ZAMQP_ADMIN_FIXTURE = ZAMQP(user_id='admin')

ZAMQP_DEBUG_FIXTURE = ZAMQP(trace_on=True)
ZAMQP_ADMIN_DEBUG_FIXTURE = ZAMQP(user_id='admin', trace_on=True)

ZAMQP_ZSERVER_FIXTURE = ZAMQP(zserver=True)
ZAMQP_ZSERVER_ADMIN_FIXTURE = ZAMQP(user_id='admin', zserver=True)

ZAMQP_ZSERVER_DEBUG_FIXTURE = ZAMQP(zserver=True, trace_on=True)
ZAMQP_ZSERVER_ADMIN_DEBUG_FIXTURE = ZAMQP(user_id='admin',
                                          zserver=True, trace_on=True)


# ZAMQP internal test fixture

class Testing(Layer):
    defaultBases = (RABBIT_FIXTURE, z2.STARTUP)

    def setUp(self):
        # Push a new configuration context so that it's possible to re-import
        # ZCML files after tear-down (in Plone tests, PloneSandboxLayer does
        # this for you)
        self['configurationContext'] = configurationContext = (
            zca.stackConfigurationContext(self['configurationContext'],
            name='ZAMQP-Testing'))
        zca.pushGlobalRegistry()

        xmlconfig.file('testing.zcml', collective.zamqp,
                       context=self['configurationContext'])

    def tearDown(self):
        zca.popGlobalRegistry()
        del self['configurationContext']

TESTING_FIXTURE = Testing()

ZAMQP_INTEGRATION_TESTING = z2.IntegrationTesting(
    bases=(TESTING_FIXTURE, ZAMQP_FIXTURE),
    name='ZAMQP:Integration')

ZAMQP_FUNCTIONAL_TESTING = z2.FunctionalTesting(
    bases=(TESTING_FIXTURE, ZAMQP_FIXTURE),
    name='ZAMQP:Functional')
