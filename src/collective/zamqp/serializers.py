# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyright (c) 2012 University of Jyväskylä and Contributors.
###
"""Named serializer utilities"""

from grokcore import component as grok

from collective.zamqp.interfaces import ISerializer

import cPickle


class PlainTextSerializer(grok.GlobalUtility):
    grok.provides(ISerializer)
    grok.name("text")

    content_type = "text/plain"

    def serialize(self, body):
        return body

    def deserialize(self, body):
        return body


class PlainTextSerializerAlias(PlainTextSerializer):
    grok.provides(ISerializer)
    grok.name("plain")


class PlainTextSerializerByMimeType(PlainTextSerializer):
    grok.provides(ISerializer)
    grok.name(PlainTextSerializer.content_type)


class PickleSerializer(grok.GlobalUtility):
    grok.provides(ISerializer)
    grok.name("pickle")

    content_type = "application/x-python-serialize"

    def serialize(self, body):
        return cPickle.dumps(body)

    def deserialize(self, body):
        return cPickle.loads(body)


class PickleSerializerByMimeType(PickleSerializer):
    grok.provides(ISerializer)
    grok.name(PickleSerializer.content_type)


try:
    import msgpack

    class MessagePackSerializer(grok.GlobalUtility):
        grok.provides(ISerializer)
        grok.name("msgpack")

        content_type = "application/x-msgpack"

        def serialize(self, body):
            return msgpack.packb(body)

        def deserialize(self, body):
            return msgpack.unpackb(body)

    class MessagePackSerializerByMimeType(MessagePackSerializer):
        grok.provides(ISerializer)
        grok.name(MessagePackSerializer.content_type)

except ImportError:
    pass


try:
    try:
        import simplejson as json
        json  # pyflakes
    except ImportError:
        import json

    class JSONSerializer(grok.GlobalUtility):
        grok.provides(ISerializer)
        grok.name("json")

        content_type = "application/x-json"

        def serialize(self, body):
            return json.dumps(body)

        def deserialize(self, body):
            return json.loads(body)

    class JSONSerializerByMimeType(JSONSerializer):
        grok.provides(ISerializer)
        grok.name(JSONSerializer.content_type)

    class JSONSerializerByMimeTypeAlias(JSONSerializer):
        grok.provides(ISerializer)
        grok.name("application/json")

except ImportError:
    pass
