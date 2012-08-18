# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyright (c) 2012 University of Jyväskylä and Contributors.
###
# This module is a derivate of affinitic.zamqp.connection.
#
# Copyright by Affinitic sprl
###
"""Command line producer to publish test messages"""

import sys
import getopt

from pika import\
      PlainCredentials, ConnectionParameters, SelectConnection,\
      BasicProperties


def usage():
    print """
    Usage: publishmsg [-h | -o hostname -t port -v (virtual_host)
           -u (username) -p (password) -e (exchange) -r (routing_key)
           -m (message)]

    Options:

        -h / --help
            Print thiѕ help message

        -o hostname / --hostname=host
            Hostname where the message broker is running

        -t port / --port=port_number
            Port Number of the message broker (defaults to 5672)

        -v virtual_host / --virtual-host=virtual_host
            Virtual host id

        -u username / --user=username
            Connection Username

        -p password / --password=password
            Connection Password

        -e exchange_name / --exchange=exchange_name
            Exchange name

        -r routing_key / --routing-key=routing_key
            Routing key id

        -m message / --message=message
            Message
"""


def getCommandLineConfig():
    opts = []
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ho:t:v:u:p:e:r:m:',
            ['help', 'hostname=', 'port=', 'virtual-host', 'username=',
             'password=', 'exchange=', 'routing-key=', 'message='])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)
    host = None
    port = 5672
    virtual_host = None
    username = None
    password = None
    exchange = None
    routing_key = None
    message = None
    if len(opts) == 0:
        usage()
        sys.exit(2)
    for o, value in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit()
        elif o in ('-o', '--hostname'):
            host = value
        elif o in ('-t', '--port'):
            port = int(value)
        elif o in ('-u', '--username'):
            username = value
        elif o in ('-p', '--password'):
            password = value
        elif o in ('-v', '--virtual-host'):
            virtual_host = value
        elif o in ('-e', '--exchange'):
            exchange = value
        elif o in ('-r', '--routing-key'):
            routing_key = value
        elif o in ('-m', '--message'):
            message = value
    return (host, port, virtual_host, username, password,
            exchange, routing_key, message)


def main():

    class BasicPublish(object):
        """See also: http://pika.github.com/examples.html"""

        def __init__(self, host, port, virtual_host, username, password,
                     exchange, routing_key, message):
            self.channel = None
            self.exchange = exchange
            self.routing_key = routing_key
            self.message = message

            credentials = PlainCredentials(
                username, password, erase_on_connect=False)

            parameters = ConnectionParameters(
                host, port, virtual_host, credentials=credentials)

            self.connection = SelectConnection(
                parameters=parameters, on_open_callback=self.on_connect)

        def on_connect(self, connection):
            self.connection.channel(self.on_channel_open)

        def on_channel_open(self, channel):
            self.channel = channel
            self.channel.exchange_declare(exchange=self.exchange,
                                          type='direct', durable=True,
                                          auto_delete=False,
                                          callback=self.on_exchange_declared)

        def on_exchange_declared(self, frame):
            self.channel.queue_declare(queue=self.routing_key, durable=True,
                                       exclusive=False, auto_delete=False,
                                       callback=self.on_queue_declared)

        def on_queue_declared(self, frame):
            self.channel.queue_bind(exchange=self.exchange,
                                    queue=self.routing_key,
                                    routing_key=self.routing_key,
                                    callback=self.on_queue_bound)

        def on_queue_bound(self, frame):
            properties = BasicProperties(content_type='text/plain',
                                         delivery_mode=1)
            self.channel.basic_publish(exchange=self.exchange,
                                       routing_key=self.routing_key,
                                       body=self.message,
                                       properties=properties)
            self.connection.close()

    basic_publish = BasicPublish(*getCommandLineConfig())
    try:
        basic_publish.connection.ioloop.start()
    except KeyboardInterrupt:
        basic_publish.connection.close()
        basic_publish.connection.ioloop.start()


if __name__ == '__main__':
    main()
