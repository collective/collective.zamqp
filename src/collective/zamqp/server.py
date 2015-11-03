# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyright (c) 2012 University of Jyväskylä and Contributors.
###
# This module is a derivate of a work by Chris McDonough for Zope ClockServer.
#
# Copyright (c) 2005 Chris McDonough. All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
###
"""AMQP consuming server, which generates a faux HTTP request for every
consumed message by adopting the asyncore API"""
from ZPublisher.HTTPRequest import HTTPRequest
from ZServer.HTTPResponse import make_response
from ZServer.PubCore import handle
from ZServer.medusa.default_handler import unquote
from ZServer.medusa.http_server import http_request
from collective.zamqp.interfaces import IBeforeBrokerConnectEvent
from collective.zamqp.interfaces import IBrokerConnection
from collective.zamqp.interfaces import IConsumer
from collective.zamqp.interfaces import IConsumingRequest
from collective.zamqp.utils import logger
from zope.component import getUtilitiesFor
from zope.component import getUtility
from zope.component import provideHandler
from zope.component import provideUtility
from zope.interface import implements
import StringIO
import os
import posixpath
import socket
import time


class AMQPMedusaLogger:
    """Simple Medusa compatible logger wrapper
    """
    def __init__(self, logger):
        self.logger = logger

    def log(self, ip, msg, **kw):
        self.logger.log(ip + ' ' + msg)


class AMQPMedusaChannel:
    """Dummy medusa channel
    """
    addr = ['127.0.0.1']
    closed = 1

    def __init__(self, server):
        self.server = server

    def push_with_producer(self):
        pass

    def close_when_done(self):
        pass


class AMQPRequest(HTTPRequest):
    """A special HTTPRequest, which carries an AMQP-message, any additional
    information for its processing and provides IConsumingRequest-marker
    interface"""
    implements(IConsumingRequest)

    retry_max_count = 0


class ConsumingServer(object):
    """AMQP Consuming Server"""

    # prototype request environment
    _ENV = dict(REQUEST_METHOD='GET',
                SERVER_PORT='AMQP',
                SERVER_NAME='AMQP Consuming Server',
                SERVER_SOFTWARE='Zope',
                SERVER_PROTOCOL='HTTP/1.0',
                SCRIPT_NAME='',
                GATEWAY_INTERFACE='CGI/1.1',
                REMOTE_ADDR='0')

    # required by ZServer
    SERVER_IDENT = 'AMQP'

    # Use VirtualHostMonster
    _USE_VHM = True

    def __init__(self, connection_id, site_id, user_id='Anonymous User',
                 scheme='http', hostname=None, port=80, use_vhm=True,
                 vhm_method_prefix='', logger=None, handler=None):

        self.logger = AMQPMedusaLogger(logger)

        from collective.zamqp.utils import logger
        logger.default(
            u"AMQP Consuming Server for connection '%s' started "
            u"(site '%s' user: '%s')",
            connection_id, site_id, user_id)

        self._USE_VHM = use_vhm

        h = self.headers = []
        h.append('User-Agent: AMQP Consuming Server')
        h.append('Accept: text/html,text/plain')
        if not hostname:
            hostname = socket.gethostname()
        if use_vhm or ':' in hostname:
            h.append('Host: {0:s}'.format(hostname))
        else:
            h.append('Host: {0:s}:{1:d}'.format(hostname, port))

        self.hostname = hostname
        self.connection_id = connection_id
        self.site_id = site_id
        self.user_id = user_id
        self.port = port
        self.scheme = scheme
        self.vhm_method_prefix = vhm_method_prefix

        if handler is None:
            # for unit testing
            handler = handle
        self.zhandler = handler

        self.consumers = []
        provideHandler(self.on_before_broker_connect,
                       [IBeforeBrokerConnectEvent])

    def get_requests_and_response(self, message):
        # All ZAMQP-requests are send to the same 'zamqp-consumer'-view. To
        # enhance the resulting transaction undo log, we append the view path
        # with message related details so that the full undo log path will be
        # @@zamqp-consumer/connection_id/exchange/routing_key[/correlation_id]
        exchange = getattr(message.method_frame, 'exchange', '') or '(default)'
        routing_key = getattr(message.method_frame, 'routing_key', '')
        correlation_id = getattr(message.header_frame, 'correlation_id', '')

        _params = (exchange, routing_key)
        if self._USE_VHM and self.vhm_method_prefix:
            _method = \
                self.vhm_method_prefix + \
                "/@@zamqp-consumer/{self.connection_id}/{0}/{1}"
        elif self._USE_VHM:
            _method = \
                "/VirtualHostBase" + \
                "/{self.scheme}/{self.hostname}:{self.port}/{self.site_id}" + \
                "/VirtualHostRoot" + \
                "/@@zamqp-consumer/{self.connection_id}/{0}/{1}"
        else:
            _method = \
                "/{self.site_id}" + \
                "/@@zamqp-consumer/{self.connection_id}/{0}/{1}"

        if correlation_id:
            _method += "/{2}"
            _params += (correlation_id, )

        method = _method.format(self=self, *_params)

        out = StringIO.StringIO()
        s_req = '%s %s HTTP/%s' % ('GET', method, '1.0')
        req = http_request(AMQPMedusaChannel(self), s_req, 'GET', method,
                           '1.0', self.headers)
        env = self.get_env(req)
        resp = make_response(req, env)

        env['AMQP_MESSAGE'] = message
        env['AMQP_USER_ID'] = self.user_id
        zreq = AMQPRequest(out, env, resp)

        # TODO: We may need some abstraction here to support custom PAS-plugins
        # for authentication of AMQP-requests.
        #
        # The following default __ac-cookie support works only for the default
        # Plone 4.x-setup, for authenticating messages between Plone-sites with
        # the same plone.session shared secret. It could also be used for
        # authenticating web-stomp-origin requests, but in reality, there is no
        # safe way to give the web-stomp-javascript access the value of the
        # current __ac-cookie value.
        headers = getattr(message.header_frame, 'headers', {}) or {}
        x_cookie_auth = headers.get('x-cookie-auth', None)
        if x_cookie_auth:
            zreq.cookies['__ac'] = x_cookie_auth

        return req, zreq, resp

    def get_env(self, req):
        env = self._ENV.copy()
        (path, params, query, fragment) = req.split_uri()
        if params:
            path = path + params  # undo medusa bug
        while path and path[0] == '/':
            path = path[1:]
        if '%' in path:
            path = unquote(path)
        if query:
            # ZPublisher doesn't want the leading '?'
            query = query[1:]
        env['PATH_INFO'] = '/' + path
        env['PATH_TRANSLATED'] = posixpath.normpath(
            posixpath.join(os.getcwd(), env['PATH_INFO']))
        if query:
            env['QUERY_STRING'] = query
        env['channel.creation_time'] = time.time()
        for header in req.header:
            key, value = header.split(":", 1)
            key = key.upper()
            value = value.strip()
            key = 'HTTP_%s' % ("_".join(key.split("-")))
            if value:
                env[key] = value
        return env

    def on_before_broker_connect(self, event=None):
        self.consumers = []
        for name, consumerUtility in getUtilitiesFor(IConsumer):
            if consumerUtility.connection_id == self.connection_id:
                # To support multiple sites (multiple consuming servers for
                # a single connection) and still keep consumers simple, every
                # consuming server must get its own cloned instance of a
                # consumer.

                # Get the consumer configuration:
                kwargs = consumerUtility.__dict__.copy()  # instance properties
                kwargs = dict(k for k in kwargs.items() if k[1] is not None)

                # Substitute ${site_id} to support site specific queues:
                for key in ('queue', 'routing_key'):
                    value = getattr(consumerUtility, key, None)
                    if value and "${site_id}" in value:
                        kwargs[key] = value.replace("${site_id}", self.site_id)
                substituted_name = name.replace("${site_id}", self.site_id)

                # Clone the consumer
                params = ['connection_id',
                          'exchange',
                          'routing_key',
                          'durable',
                          'exchange_type',
                          'exchange_durable',
                          'exchange_auto_delete',
                          'exchange_auto_declare',
                          'queue',
                          'queue_durable',
                          'queue_auto_delete',
                          'queue_exclusive',
                          'queue_arguments',
                          'queue_auto_declare',
                          'auto_declare',
                          'auto_delete',
                          'auto_ack',
                          'marker']
                clonedConsumerUtility = consumerUtility.__class__(
                    **dict(k for k in kwargs.items() if k[0] in params))
                if name != substituted_name:
                    # When the consumer name contains substitution, we are
                    # able to register site specific consumers for lookup!
                    provideUtility(clonedConsumerUtility, IConsumer,
                                   name=substituted_name)

                # Append the cloned consumer:
                self.consumers.append(clonedConsumerUtility)

        self._connection = getUtility(IBrokerConnection,
                                      name=self.connection_id)
        self._connection.add_on_channel_open_callback(self.on_channel_open)

    def on_channel_open(self, channel):
        self._channel = channel
        for consumer in self.consumers:
            consumer.consume(self._channel,
                             self._connection.tx_select,
                             self.on_message_received)

    def on_message_received(self, message):
        logger.default(u"Received message '%s' sent to exchange '%s' with "
                       u"routing key '%s'",
                       message.method_frame.delivery_tag,
                       message.method_frame.exchange,
                       message.method_frame.routing_key)
        req, zreq, resp = self.get_requests_and_response(message)
        self.zhandler('Zope2', zreq, resp)
