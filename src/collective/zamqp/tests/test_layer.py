# -*- coding: utf-8 -*-
import unittest2 as unittest


from collective.zamqp.testing import (
    runAsyncTest,
    RABBIT_APP_FUNCTIONAL_TESTING,
    ZAMQP_FUNCTIONAL_TESTING,
)


class RabbitFunctional(unittest.TestCase):

    layer = RABBIT_APP_FUNCTIONAL_TESTING

    def _testNoQueues(self):
        rabbitctl = self.layer['rabbitctl']
        self.assertIn('\n'.join(rabbitctl('list_queues')),
                      ['Listing queues ...\n...done.\n\n',
                       'Listing queues ...\n\n'])

    def testNoQueues(self):
        runAsyncTest(self._testNoQueues)


class ZAMQPFunctional(unittest.TestCase):

    layer = ZAMQP_FUNCTIONAL_TESTING

    def _testDeclareQueue(self):
        rabbitctl = self.layer['rabbitctl']
        self.assertIn("my.queue\t0",
                      rabbitctl('list_queues')[0].split("\n"))

    def testDeclareQueue(self):
        runAsyncTest(self._testDeclareQueue)

    def _testDeclareQueueAgain(self):
        rabbitctl = self.layer['rabbitctl']
        self.assertIn("my.queue\t0", rabbitctl('list_queues')[0].split("\n"))

    def testDeclareQueueAgain(self):
        runAsyncTest(self._testDeclareQueueAgain)

    def _testPublishToQueue(self):
        rabbitctl = self.layer['rabbitctl']
        self.assertIn("my.queue\t1", rabbitctl('list_queues')[0].split("\n"))

    def _testPublishToQueueAndConsumeIt(self):
        rabbitctl = self.layer['rabbitctl']
        self.assertIn("my.queue\t0", rabbitctl('list_queues')[0].split("\n"))

    def testPublishToQueueAndConsumeIt(self):
        runAsyncTest(self._testDeclareQueue)

        from zope.component import getUtility
        from collective.zamqp.interfaces import IProducer
        producer = getUtility(IProducer, name="my.queue")
        producer.publish("Hello world!")

        runAsyncTest(self._testPublishToQueue)
        runAsyncTest(self._testPublishToQueueAndConsumeIt, loop_count=10)

        # from zope.testing.loggingsupport import InstalledHandler
        # handler = InstalledHandler("collective.zamqp")
        # for record in handler.records: print record.getMessage()
