collective.zamqp
================

*Asynchronous AMQP-integration for Plone (and Zope2)*

**collective.zamqp** enables asynchronous integrations between Plone and other
systems, makes it possible to avoid ZODB conflicts on serializing write
operations and allows to spawn queued asynchronous tasks from synchronous
ZPublisher-requests. **collective.zamqp** is a developer friendly
AMQP-integration for Plone. It requires an external AMQP-broker, preferably
`RabbitMQ <http://www.rabbitmq.com>`_.

.. uml::

   skinparam monochrome true

   [Site] as Site1
   [Site] as Site2
   [Service] as Service1
   [Service] as Service2
   [Broker] as Broker

   Site1 .right.> Broker
   Broker .left.> Site1

   Site2 .down.> Broker
   Broker .up.> Site2

   Broker .right.> Service1
   Service1 .left.> Broker

   Broker .down.> Service2
   Service2 .up.> Broker

**collective.zamqp** acts as a *Zope Server* by co-opting Zope's asyncore
mainloop and injecting consumed messages as *requests* to be handled by
ZPublisher (exactly like Zope ClockServer). Therefore AMQP-messages are handled
(by default) in a similar environment to regular HTTP-requests: ZCA-hooks,
events and everything else behaving normally.

**collective.zamqp** is an almost complete rewrite of affinitic.zamqp
`<http://pypi.python.org/pypi/affinitic.zamqp>`_, but preserves its ideas on how
to setup AMQP-routing with simple grok-based configuration of connections,
producers and consumers.

*collective.zamqp* relies on asyncore-supporting AMQP-library `pika
<http://pypi.python.org/pypi/pika>`_.

.. toctree::
   :maxdepth: 3

   introduction

While we are still documenting and testing **collective.zamqp**,
you may want to take a look at `collective.zamqpdemo
<http://github.com/datakurre/collective.zamqpdemo/>`_ for examples.
