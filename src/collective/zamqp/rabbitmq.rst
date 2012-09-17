RabbitMQ
========

Even it's preferred to install `RabbitMQ <http://www.rabbitmq.com/>`_ by
following the practices of your system, it's also possible to install it (with
or without erlang) into your development buildout. Here's an example
``./buildout.cfg`` for compiling RabbitMQ into its own buildout::

    [buildout]
    parts =
        erlang
        rabbitmq

    [erlang]
    recipe = zc.recipe.cmmi
    url = http://www.erlang.org/download/otp_src_R14B04.tar.gz
    # Allows erlang to compile on OSX:
    environment =
        CFLAGS=-O0
    # Removes 'unhandled FPE'-errors OSX:
    configure-options =
        --disable-fp-exceptions
        --prefix=${buildout:parts-directory}/erlang

    [rabbitmq]
    recipe = rod.recipe.rabbitmq
    erlang-path = ${erlang:location}/bin
    url = http://www.rabbitmq.com/releases/rabbitmq-server/v2.8.2/rabbitmq-server-2.8.2.tar.gz

RabbitMQ is shipped with many interesting plugins. Actually, you shouldn't
learn RabbitMQ without trying out its
`management plugin <http://www.rabbitmq.com/management.html>`_.
With the buildout configuration above, you can enable the management plugin by
adding the following two files under your buildout directory.

At first, ``./etc/rabbitmq-env.conf``::

    RABBITMQ_PLUGINS_DIR=${RABBITMQ_HOME}/plugins
    RABBITMQ_ENABLED_PLUGINS_FILE=${RABBITMQ_HOME}/../../etc/rabbitmq-plugins

and then ``./etc/rabbit-plugins``::

    [rabbitmq_management].

With these files and, of course, ``bootstrap.py`` in place, you could install
and start your RabbitMQ-broker with::

    $ ./python bootstrap.py
    $ bin/buildout
    $ source bin/rabbitmq-env
    $ bin/rabbitmq-server

And if you decided to activate the mangement plugin, it should be now available
at http://localhost:55672/.
