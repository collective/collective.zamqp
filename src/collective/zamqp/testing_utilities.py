# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyrighted by University of Jyväskylä and Contributors.
###
"""Test utilities"""

from grokcore import component as grok

from collective.zamqp.connection import BrokerConnection
from collective.zamqp.producer import Producer


class TestConnection(BrokerConnection):
    grok.name("test.connection")


class SimpleProducer(Producer):
    grok.name("my.queue")

    connection_id = "test.connection"
    queue = "my.queue"

