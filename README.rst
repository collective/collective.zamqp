.. image:: https://travis-ci.org/collective/collective.zamqp.png
   :target: http://travis-ci.org/collective/collective.zamqp

AMQP integration for Zope2 (and Plone)
======================================

**collective.zamqp** acts as a *Zope Server* by co-opting Zope's asyncore
mainloop (using asyncore-supporting AMQP-library
`pika <http://pypi.python.org/pypi/pika>`_),
and injecting consumed messages as *requests* to be handled by ZPublisher
(exactly like Zope ClockServer).

Therefore AMQP-messages are handled (by default) in a similar environment to
regular HTTP-requests: ZCA-hooks, events and everything else behaving normally.

This package is an almost complete rewrite of
`affinitic.zamqp <http://pypi.python.org/pypi/affinitic.zamqp>`_,
but preserves its ideas on how to setup AMQP-messaging
by configuring only producers and consumers.

TODO
    * rewrite documentation to reflect the new design
    * update affinitic.zamqp's tests for the new design

While we are still documenting and testing **collective.zamqp**,
you may want to take a look at `collective.zamqpdemo
<http://github.com/datakurre/collective.zamqpdemo/>`_ for an example of use.


Installation
============

A common setup includes a producer and a worker instance which are both
connected to the same rabbitmq server.

Buildout
--------

Both instances can be easily configured using buildout::

    [buildout]
    parts =
        instance
        worker

    ...

    [instance]
    recipe = plone.recipe.zope2instance
    http-address = 8080
    eggs =
        ...
        collective.zamqp

    ...
    zope-conf-additional =
        %import collective.zamqp
        <amqp-broker-connection>
            connection_id   superuser
            hostname        my.rabbithostname.com
            port            5672
            username        guest
            password        guest
            heartbeat       120
            keepalive       60
        </amqp-broker-connection>

    [worker]
    <= instance
    http-address = 8081
    zserver-threads = 1
    environment-vars =
        ZAMQP_LOGLEVEL INFO
    zope-conf-additional =
        ${instance:zope-conf-additional}
        <amqp-consuming-server>
            connection_id   superuser
            site_id         Plone
            user_id         admin
        </amqp-consuming-server>

Explanation of configuration parameters
---------------------------------------

- amqp-broker-connection

  ``connection_id``
        Connection id, which is the registered name of the created
        global BrokerConnection-utility.
  ``hostname``  (optional)
        Hostname or IP Address of RabbitMQ server to connect to, default to
        ``localhost``.
  ``port``  (optional)
        TCP port of RabbitMQ server to connect to, defaults to ``5672``.
  ``virtual_host``  (optional)
        RabbitMQ virtual host to use, defaults to ``/``.
  ``username``  (optional)
        Plain text username for RabbitMQ connection, defaults to ``guest``.
  ``password``  (optional)
        Plain text password for RabbitMQ connection, defaults to ``guest``.
  ``heartbeat``  (optional)
        AMQP heartbeat interval in seconds, defaults to ``0`` to disable
        heartbeat.
  ``keepalive``  (optional)
        Register producer, consumer, view and clock-server with the given
        integer timeout in seconds to keep the connection alive. Defaults
        ``0``.
  ``prefetch_count`` (optional)
        AMQP channel prefetch count limit, defaults to 0 for no limit.

- amqp-consuming-server

  ``connection_id``
        The name of a global utility providing configured IBrokerConnection. A
        consuming server will serve consumers registered for its connection id
        only.
  ``scheme``  (optional)
        Configure URL schema for virtual rewriting using VirtualHostMonster,
        default is ``http``. Will be ignored if no ``hostname`` is given.
  ``hostname``  (optional)
        Hostname which will be passed into fake request. When calling
        ``object.absolute_url()`` in a consuming server you'll receive this
        hostname. URL will be rewritten using VirtualHostMonster using following
        scheme::

            /VirtualHostBase/{scheme}/{hostname}:{port}/{site_id}/VirtualHostRoot/...

        If a hostname is configured, VirtualHostMonster will be invoked,
        ``socket.gethostname()`` will be used else.
  ``port`` (optional)
        Configure port for virtual rewriting using VirtualHostMonster,
        default is ``80``. Will be ignored if no ``hostname`` is given.
  ``use_vhm`` (optional)
       Create VirtualHostMonster-wrapped method calls when hostname is set. VHM
       is used to tell portal the configured real public hostname and to hide
       portal's id from path. Defaults to *on*.
  ``vhm_method_prefix`` (optional)
       Explicitly set the VHM method prefix for AMQP-based requests. Most
       typical options may look like:

       * /VirtualHostBase/https/example.com:443/Plone
       * /VirtualHostBase/https/example.com:443/Plone/VirtualHostRoot
       * /VirtualHostBase/https/example.com:443/Plone/VirtualHostRoot/_vh_subsite

       Note: This overrides the default implicit VHM-support by setting scheme,
       hostname, port and use_vhm, but will still require use_vhm enabled to be
       active. Empty value fallbacks to the old default use_vhm-behavior.
  ``site_id``
        The id of a site, which should be the context when consuming the AMQP
        messages, which the consumers of a consuming server consume. If a
        ``hostname`` is given, this will be used for VirtualHostMonster
        rewrites.
  ``user_id``  (optional)
        Optional user id of the Plone user, whose privileges are used to consume
        the messages. By default, the messages are consumed as Anonymous User
        calling trusted filesystem code.


Configuring logging
-------------------

You may want to in/decrease ``collective.zamqp`` loglevel which can easily be
done by passing an environment variable into worker instance as seen in
buildout example above::

    [worker]
    ...
    environment-vars =
        ZAMQP_LOGLEVEL INFO
    ...

Valid parameters are:

- DEBUG
- INFO
