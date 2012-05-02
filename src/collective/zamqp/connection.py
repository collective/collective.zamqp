# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the GPL license, see LICENCE.txt for more details.
#
# Copyright by Affinitic sprl
# Copyright (c) 2012 University of Jyväskylä
###
"""Broker connection utility base class providing Pika's AsyncoreConnection"""

import time
import random
import socket
import asyncore
import threading

import grokcore.component as grok

from zope.component import getUtilitiesFor
from zope.interface import implements
from zope.event import notify

from pika import PlainCredentials, ConnectionParameters
from pika.adapters.asyncore_connection import\
    AsyncoreDispatcher as AsyncoreDispatcherBase
from pika.adapters.asyncore_connection import\
    AsyncoreConnection as AsyncoreConnectionBase
from pika.callback import CallbackManager
from pika.simplebuffer import SimpleBuffer

from collective.zamqp.interfaces import\
    IBrokerConnection, IBeforeBrokerConnectEvent

import logging
logger = logging.getLogger('collective.zamqp')


class AsyncoreScheduling(asyncore.dispatcher):

    def __init__(self, callback, timeout):
        asyncore.dispatcher.__init__(self)

        self.deadline = time.time() + timeout
        self.callback = callback

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)

    def readable(self):
        if time.time() >= self.deadline:
            self.close()
            self.callback()
        return False

    def handle_connect(self):
        pass

    def handle_read(self):
        return True

    def handle_write(self):
        return True

    def writable(self):
        return False

    def handle_error(self):
        pass


class LockingSimpleBuffer(SimpleBuffer):

    def __init__(self, data=None):
        super(LockingSimpleBuffer, self).__init__(data)
        self.lock = threading.Lock()

    def write(self, *data_strings):
        """
        Append given strings to the buffer.
        """
        with self.lock:
            return super(LockingSimpleBuffer, self).write(*data_strings)

    def read(self, size=None):
        """
        Read the data from the buffer, at most 'size' bytes.
        """
        with self.lock:
            return super(LockingSimpleBuffer, self).read(size)

    def consume(self, size):
        """
        Move pointer and discard first 'size' bytes.
        """
        with self.lock:
            return super(LockingSimpleBuffer, self).consume(size)

    def read_and_consume(self, size):
        """
        Read up to 'size' bytes, also remove it from the buffer.
        """
        with self.lock:
            return super(LockingSimpleBuffer, self).read_and_consume(size)

    def send_to_socket(self, sd):
        """
        Faster way of sending buffer data to socket 'sd'.
        """
        with self.lock:
            return super(LockingSimpleBuffer, self).send_to_socket(sd)

    def flush(self):
        """
        Remove all the data from buffer.
        """
        with self.lock:
            return super(LockingSimpleBuffer, self).flush()


class AsyncoreDispatcher(AsyncoreDispatcherBase):
    __doc__ = AsyncoreDispatcherBase.__doc__

    def handle_read(self):
        AsyncoreDispatcherBase.handle_read(self)
        self._process_timeouts()


class AsyncoreConnection(AsyncoreConnectionBase):
    __doc__ = AsyncoreConnectionBase.__doc__

    def __init__(self, parameters=None, on_open_callback=None,
                 reconnection_strategy=None):
        super(AsyncoreConnection, self).__init__(
            parameters, on_open_callback, reconnection_strategy)
        self.lock = threading.Lock()

    def _adapter_connect(self, host, port):
        """
        Connect to our RabbitMQ boker using AsyncoreDispatcher, then setting
        Pika's suggested buffer size for socket reading and writing. We pass
        the handle to self so that the AsyncoreDispatcher object can call back
        into our various state methods.
        """
        self.ioloop = AsyncoreDispatcher(host, port)

        # Map some core values for compatibility
        self.ioloop._handle_error = self._handle_error
        self.ioloop.connection = self
        self.ioloop.suggested_buffer_size = self._suggested_buffer_size
        self.socket = self.ioloop.socket

    def _send_method(self, channel_number, method, content=None):
        with self.lock:
            return super(AsyncoreConnection, self)._send_method(
                channel_number, method, content)

    # We never disconnect on purpose. Therefore we've overridden both
    # _adapter_disconnect and _handle_disconnect to close connection completely
    # and process _on_connection_closed-callbacks to trigger reconnecting
    # procedure.

    def _adapter_disconnect(self):
        """
        Called if we are forced to disconnect for some reason from Connection
        """
        # Remove from the IOLoop
        self.ioloop.stop()

        # Close our socket
        self.socket.close()

        # Close up our Connection state
        self._on_connection_closed(None, True)

    def _handle_disconnect(self):
        """
        Called internally when we know our socket is disconnected already
        """
        # Remove from the IOLoop
        self.ioloop.stop()

        # Close our socket
        self.socket.close()

        # Close up our Connection state
        self._on_connection_closed(None, True)

    def _init_connection_state(self):
        super(AsyncoreConnection, self)._init_connection_state()
        self.outbound_buffer = LockingSimpleBuffer()


class BrokerConnection(grok.GlobalUtility):
    """Connection utility base class"""

    grok.implements(IBrokerConnection)
    grok.baseclass()

    connection_id = None

    hostname = 'localhost'
    port = 5672
    virtual_host = '/'

    username = 'guest'
    password = 'guest'

    heartbeat = 0
    tx_select = False  # Be aware, that rollback for transactional channel
                       # is safe to use (and tx_select useful) only on
                       # dedicated single-threaded AMQP-consuming ZEO-clients.

    def __init__(self, connection_id=None, hostname=None, port=None,
                 virtual_host=None, username=None, password=None,
                 heartbeat=None, tx_select=None):

        # allow class variables to provide defaults
        self.connection_id = connection_id or self.connection_id

        self.hostname = hostname or self.hostname
        self.port = port or self.port
        self.virtual_host = virtual_host or self.virtual_host

        self.username = username or self.username
        self.password = password or self.password

        if heartbeat is not None:
            self.heartbeat = heartbeat

        if tx_select is not None:
            self.tx_select = tx_select

        self._callbacks = CallbackManager()
        self._reconnection_delay = 1.0

        # BBB for affinitic.zamqp
        if getattr(self, 'userid', None):
            from zope.deprecation import deprecated
            self.username = self.userid
            self.userid =\
                deprecated(self.userid,
                           ('Connection.userid is no more. '
                            'Please, use Connection.username instead.'))

    def connect(self):
        credentials = PlainCredentials(
            self.username, self.password, erase_on_connect=False)
        parameters = ConnectionParameters(
            self.hostname, self.port, self.virtual_host,
            credentials=credentials,
            heartbeat=self.heartbeat and True or False)
        # AMQP-heartbeat timeout must be set manually due to bug in pika 0.9.5:
        if parameters.heartbeat:
            parameters.heartbeat = int(self.heartbeat)
        self._connection = AsyncoreConnection(
            parameters=parameters,
            on_open_callback=self.on_connect)
        self._reconnection_timeout = None
        self._connection.add_on_close_callback(self.reconnect)

    def reconnect(self, conn=None):
        if not getattr(self, '_reconnection_timeout', None):
            conn_id = self.connection_id or\
                getattr(self, 'grokcore.component.directive.name', 'n/a')
            logger.info("Trying to reconnect connection '%s' in %s seconds",
                        conn_id, self._reconnection_delay)
            self._reconnection_timeout =\
                AsyncoreScheduling(self.connect, self._reconnection_delay)
            self._reconnection_delay *= (random.random() * 0.5) + 1.0
            self._reconnection_delay = min(self._reconnection_delay, 60.0)

    @property
    def is_open(self):
        return getattr(self._connection, 'is_open', False)

    def add_on_channel_open_callback(self, callback):
        self._callbacks.add(0, '_on_channel_open', callback, False)

    def on_connect(self, connection):
        self._connection = connection
        self._connection.channel(self.on_channel_open)
        self._reconnection_delay = 1.0

    def on_channel_open(self, channel):
        self._channel = channel
        self._channel.add_on_close_callback(self.on_channel_closed)
        if self.tx_select:
            channel.tx_select(self.on_channel_tx_select)
        else:
            self._callbacks.process(0, '_on_channel_open', self, self._channel)

    def on_channel_closed(self, code, text):
        logger.warning("Channel closed with reason '%s %s'",
                       code, text)
        self._connection.close(code, text)
        self.reconnect()

    def on_channel_tx_select(self, frame):
        self._callbacks.process(0, '_on_channel_open', self, self._channel)


class BeforeBrokerConnectEvent(object):
    implements(IBeforeBrokerConnectEvent)


def connect_all(event=None):
    """Connect all connections, which have related utilities registered"""

    # Notify all, who want to register callbacks for connections
    notify(BeforeBrokerConnectEvent())

    # Gather all producer and consumer utility registrations
    from collective.zamqp.interfaces import IProducer, IConsumer
    regs = list(getUtilitiesFor(IProducer)) + list(getUtilitiesFor(IConsumer))

    # Connect all connections, which have related utilities registered
    for connection_id, connection in getUtilitiesFor(IBrokerConnection):
        if filter(lambda reg: reg[1].connection_id == connection_id, regs):
            connection.connect()
