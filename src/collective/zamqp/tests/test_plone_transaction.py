# -*- coding: utf-8 -*-
from collective.zamqp.consumer import Consumer
from collective.zamqp.interfaces import IMessageArrivedEvent
from collective.zamqp.interfaces import IProducer
from collective.zamqp.producer import Producer
from collective.zamqp.testing import runAsyncTest
from collective.zamqp.testing import ZAMQP
from grokcore import component as grok
from plone.app.testing import FunctionalTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.testing import z2
from zope.component import getUtility
from zope.configuration import xmlconfig
from zope.interface import Interface
import collective.zamqp
import time
import transaction
import unittest2 as unittest

try:
    import plone.app.contenttypes
    HAS_PLONE_APP_CONTENTTYPES = True
except:
    HAS_PLONE_APP_CONTENTTYPES = False


class ITestMessage(Interface):
    """Message marker interface"""


class TestProducer(Producer):
    grok.name('my.queue')

    connection_id = 'test.connection'
    queue = 'my.queue'

    serializer = 'text/plain'


class TestConsumer(Consumer):
    grok.name('my.queue')

    connection_id = 'test.connection'
    queue = 'my.queue'

    marker = ITestMessage


@grok.subscribe(ITestMessage, IMessageArrivedEvent)
def received(message, event):
    from zope.component.hooks import getSite
    portal = getSite()
    portal.invokeFactory('Folder', id='test-folder', title=message.body)
    message.ack()


class PloneMessagingLayer(PloneSandboxLayer):
    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        self.loadZCML(package=collective.zamqp)
        xmlconfig.string("""\
<configure xmlns="http://namespaces.zope.org/zope"
           xmlns:grok="http://namespaces.zope.org/grok">

    <grok:grok package="collective.zamqp.tests.test_plone_transaction"/>

</configure>""", context=configurationContext)
        if HAS_PLONE_APP_CONTENTTYPES:
            self.loadZCML(package=plone.app.contenttypes)

    def setUpPloneSite(self, portal):
        if HAS_PLONE_APP_CONTENTTYPES:
            self.applyProfile(portal, 'plone.app.contenttypes:default')


PLONE_MESSAGING_FIXTURE = PloneMessagingLayer()

ZAMQP_ZSERVER_TESTUSER_FIXTURE = ZAMQP(user_id=TEST_USER_NAME, zserver=True)

PLONE_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(PLONE_MESSAGING_FIXTURE,
           ZAMQP_ZSERVER_TESTUSER_FIXTURE),
    name='PloneMessagingLayer:Functional')


class TestPloneTransaction(unittest.TestCase):

    layer = PLONE_FUNCTIONAL_TESTING

    def setUp(self):
        setRoles(self.layer['portal'], TEST_USER_ID, ['Contributor', 'Editor'])
        transaction.commit()

    def testFolderCreation(self):
        def untilDeclared():
            self.assertIn(
                'my.queue\t0',
                self.layer['rabbitctl']('list_queues')[0].split('\n')
            )
        runAsyncTest(untilDeclared)

        def noFolder():
            self.layer['portal']._p_jar.sync()
            self.assertNotIn('test-folder', self.layer['portal'].objectIds())

        noFolder()  # No folder before dispatch

        producer = getUtility(IProducer, name='my.queue')
        producer.register()  # register for transaction
        producer.publish('Hello World!')

        def notPublished():
            self.assertNotIn(
                'my.queue\t1',
                self.layer['rabbitctl']('list_queues')[0].split('\n')
            )

        runAsyncTest(notPublished)

        transaction.commit()

        def untilPublished():
            self.assertIn(
                'my.queue\t1',
                self.layer['rabbitctl']('list_queues')[0].split('\n')
            )
        runAsyncTest(untilPublished)

        def untilConsumed():
            self.assertIn(
                'my.queue\t0',
                self.layer['rabbitctl']('list_queues')[0].split('\n')
            )
        runAsyncTest(untilConsumed, loop_count=10)

        self.layer['portal']._p_jar.sync()
        self.assertIn('test-folder', self.layer['portal'].objectIds())

        self.assertEqual(
            self.layer['portal']['test-folder'].title, u'Hello World!')
        self.assertIn(
            TEST_USER_ID, self.layer['portal']['test-folder'].Creator())
