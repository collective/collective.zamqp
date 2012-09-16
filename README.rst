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

.. image:: https://secure.travis-ci.org/datakurre/collective.zamqp.png
     :target: http://travis-ci.org/datakurre/collective.zamqp
