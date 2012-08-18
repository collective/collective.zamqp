# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyrighted by University of Jyväskylä and Contributors.
###
"""Test fixtures"""

from zope.configuration import xmlconfig

from plone.testing import Layer, z2

from rabbitfixture.server import (
    RabbitServer,
    RabbitServerResources
    )


class FixedHostname(RabbitServerResources):
    """Allocate the resources a RabbitMQ server needs with the explicitly
    defined hostname.
    (Does not query the hostname from a socket as the default implementation
    does.)
    """

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

        from zope.component import getUtility
        from collective.zamqp.interfaces import IBrokerConnection
        connection = getUtility(IBrokerConnection, name="test.connection")
        connection.port = self['rabbit'].config.port

        # from collective.zamqp import connection
        # connection.connect_all()

    def tearDown(self):
        pass


ZAMQP_FIXTURE = ZAMQP()

ZAMQP_INTEGRATION_TESTING = z2.IntegrationTesting(
    bases=(ZAMQP_FIXTURE,), name='ZAMQPFixture:Integration')
ZAMQP_FUNCTIONAL_TESTING = z2.FunctionalTesting(
    bases=(ZAMQP_FIXTURE,), name='ZAMQPFixture:Functional')
