# -*- coding: utf-8 -*-
import unittest2 as unittest


from collective.zamqp.testing import (
    runAsyncTest,
    ZAMQP_FUNCTIONAL_TESTING,
)


class TestPickleSerializer(unittest.TestCase):

    layer = ZAMQP_FUNCTIONAL_TESTING

    def setUp(self):
        from testfixtures import LogCapture
        self.l = LogCapture("c.zamqp.tests")

    def tearDown(self):
        self.l.uninstall()

    def _testDeclareQueue(self):
        rabbitctl = self.layer['rabbitctl']
        self.assertIn("my.picklequeue\t0",
                      rabbitctl('list_queues')[0].split("\n"))

    def testDeclareQueue(self):
        runAsyncTest(self._testDeclareQueue)

    def _testDeclareQueueAgain(self):
        rabbitctl = self.layer['rabbitctl']
        self.assertIn("my.picklequeue\t0",
                      rabbitctl('list_queues')[0].split("\n"))

    def testDeclareQueueAgain(self):
        runAsyncTest(self._testDeclareQueueAgain)

    def _testPublishToQueue(self):
        rabbitctl = self.layer['rabbitctl']
        self.assertIn("my.picklequeue\t1",
                      rabbitctl('list_queues')[0].split("\n"))

    def _testPublishToQueueAndConsumeIt(self):
        rabbitctl = self.layer['rabbitctl']
        self.assertIn("my.picklequeue\t0",
                      rabbitctl('list_queues')[0].split("\n"))

    def testPublishToQueueAndConsumeIt(self):
        runAsyncTest(self._testDeclareQueue)

        from zope.component import getUtility
        from collective.zamqp.interfaces import IProducer
        producer = getUtility(IProducer, name="my.picklequeue")
        producer.publish({"key": "value"})

        runAsyncTest(self._testPublishToQueue)
        runAsyncTest(self._testPublishToQueueAndConsumeIt, loop_count=10)
        self.l.check(
            ('c.zamqp.tests', 'INFO',
             "<BasicProperties(['delivery_mode=2', "
             "'content_type=application/x-python-serialize'])>"),
            ('c.zamqp.tests', 'INFO', "{'key': 'value'}"),
            ('c.zamqp.tests', 'INFO', "<type 'dict'>")
        )
        # from zope.testing.loggingsupport import InstalledHandler
        # handler = InstalledHandler("collective.zamqp")
        # for record in handler.records: print record.getMessage()
