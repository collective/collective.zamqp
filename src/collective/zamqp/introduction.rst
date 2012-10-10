Introduction
============

From `Wikipedia <http://en.wikipedia.org/wiki/AMQP>`_:

    The **Advanced Message Queueing Protocol** (AMQP) is
    an open standard application protocol
    for message-oriented middleware.
    The defining features of AMQP are
    message orientation, queuing, routing
    (including point-to-point and publish-and-subscribe),
    reliability and security.

To be able to use AMQP, you usually need to setup
a separate message broker server, like `RabbitMQ <http://www.rabbitmq.com>`_.

Why is it worth of the effort?

* You may delay long-processing task to be completed asynchronously.

* You may replace synchronous RPC-calls with asynchronous messaging.

* Zope (especially ZODB) is not great in concurrent writes.
  Using AMQP-messaging those tasks could be queued and processed consecutively
  by a dedicated single threaded ZEO-client.

* You have more options on how to build integration between your services.

* A separate broker server gives you more options on
  `monitoring what's happening with your services
  <http://www.youtube.com/watch?v=CAak2ayFcV0>`_.

Using this package, your AMQP-setup could look like this:

.. uml::

   skinparam monochrome true

   Package "Plone Site A" {
       [ZEO Server] as ZEO1
       [HTTP ZEO Client] as HTTP1
       [HTTP ZEO Client] as HTTP2
       [AMQP ZEO Client] as AMQP1

       ZEO1 -down- HTTP1
       ZEO1 -down- HTTP2
       ZEO1 -down- AMQP1
   }

   Package "Plone Site B" {
       [ZEO Server] as ZEO2
       [HTTP ZEO Client] as HTTP3
       [HTTP ZEO Client] as HTTP4
       [AMQP ZEO Client] as AMQP2

       ZEO2 -up- HTTP3
       ZEO2 -up- HTTP4
       ZEO2 -up- AMQP2
   }

   Package "Broker Server" {
       [RabbitMQ]
   }

   Package "Other Application" {
       [Service]
   }

   HTTP1 .down.> [RabbitMQ]
   HTTP2 .down.> [RabbitMQ]
   AMQP1 .down.> [RabbitMQ]
   [RabbitMQ] .up.> AMQP1

   HTTP3 .up.> [RabbitMQ]
   HTTP4 .up.> [RabbitMQ]
   AMQP2 .up.> [RabbitMQ]
   [RabbitMQ] .down.> AMQP2

   [RabbitMQ] .right.> [Service]
   [Service] .left.> [RabbitMQ]

Asynchronous RPC-like AMQP-messaging between your site and an external service
may look like this:

.. uml::

   skinparam monochrome true

   site -> broker: request
   activate broker

   note left
       exchange=service.tasks
       routing_key=service.my_template
       content_type=application/x-msgpack
       body={"title": "Hello World!"}
       correlation_id=UUID
       reply_to=my_queue
   end note

   broker -> service: request
   deactivate broker
   activate service

   note left
       content_type=application/x-msgpack
       body={"title": "Hello World!"}
       correlation_id=UUID
       reply_to=my_queue
   end note

   service --> broker: response
   deactivate service
   activate broker

   note right
       exchange=service.results
       content_type=application/pdf
       body=%PDF-1.4...
       correlation_id=UUID
       routing_key=my_queue
   end note

   broker --> site: response
   deactivate broker

   note right
       content_type=application/pdf
       body=%PDF-1.4...
       correlation_id=UUID
   end note


.. What Zope integration?
.. ----------------------
.. 
.. * Using ZCA to declare producer, consumer and connection to broker. In other
.. word, create a clean Messaging Gateway [#MessagingGateway]_ to be use with zope
.. applications.
.. 
.. * Messaging with transaction support. Meaning a transactional delivery support
.. together with Zope transaction [#transaction]_ (and ZODB)
.. 
.. * Using ZCA to implement a Publish-Subscribe (aka Observer pattern) inside Zope
.. with message coming from a Queue
.. 
.. 
.. Dependencies
.. ------------
.. 
.. We use `pika <http://pypi.python.org/pypi/pika>`_ to send/receive messages and enable consumers in separate threads within Zope. We use as much as possible the API defined by `kombu <http://pypi.python.org/pypi/kombu>`_. So you might want also to read the `kombu documentation <http://github.com/ask/kombu>`_.
.. 
.. We use `grok <http://grok.zope.org>`_ to define our zope components
.. (as grok base classes).
.. This avoids us to write too much zcml.
.. 
