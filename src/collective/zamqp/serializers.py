# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyright (c) 2012 University of Jyväskylä and Contributors.
###
"""Named serializer utilities"""

import csv
import cPickle
import StringIO

from grokcore import component as grok

from collective.zamqp.interfaces import ISerializer

MSGPACK_ENCODING = 'utf-8'


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


class CSVSerializer(grok.GlobalUtility):
    """Message serializer/deserializer between unicode dictionaries and
    RFC4180 style UTF8-encoded CSV"""

    grok.provides(ISerializer)
    grok.name("csv")

    content_type = "text/csv"

    def serialize(self, body):
        assert hasattr(body, "__iter__"),\
            u"Message body must be iterable for CSV serializer."

        data = tuple(iter(body))

        assert len(data),\
            u"Message body cannot be empty (iterable) for CSV serializer."

        sample = data[0]

        assert hasattr(sample, 'iterkeys')\
            and hasattr(sample, 'itervalues')\
            and hasattr(sample, 'iteritems'),\
            u"Message items must be dictionary like objects."

        class RFC4180Dialect(csv.Dialect):
            delimiter = ','
            quotechar = '"'
            escapechar = '\\'
            lineterminator = '\r\n'
            doublequote = True
            quoting = csv.QUOTE_ALL
            skipinitialspace = False
            strict = False

        def encode(s):
            return type(s) == unicode and s.encode('utf-8') or s

        def iter_encode(iterable):
            return map(encode, iterable)

        class UTF8DictWriter(csv.DictWriter):

            def writeheader(self):
                header = dict(zip(self.fieldnames,
                                  iter_encode(self.fieldnames)))
                self.writerow(header)

            def writerow(self, row):
                row = dict(map(lambda x: (x[0], encode(x[1])),
                               row.iteritems()))
                csv.DictWriter.writerow(self, row)

        stream = StringIO.StringIO()
        writer = UTF8DictWriter(stream, iter_encode(sample.iterkeys()),
                                dialect=RFC4180Dialect)
        writer.writeheader()
        writer.writerows(data)
        return stream.getvalue()

    def deserialize(self, body):

        def decode(s):
            return type(s) == str and unicode(s, 'utf-8', 'ignore') or s

        def iter_decode(iterable):
            return map(decode, iterable)

        class UnicodeDictReader(csv.DictReader):

            def next(self):
                d = csv.DictReader.next(self)
                return dict(map(lambda x: (decode(x[0]), decode(x[1])),
                                d.iteritems()))

        stream = StringIO.StringIO()
        stream.write(body)
        stream.seek(0)
        reader = UnicodeDictReader(stream)
        return tuple(reader)


class CSVSerializerByMimeType(CSVSerializer):
    grok.provides(ISerializer)
    grok.name(CSVSerializer.content_type)


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
            return msgpack.packb(body, encoding='utf-8')

        def deserialize(self, body):
            return msgpack.unpackb(body, encoding='utf-8')

    class MessagePackSerializerByMimeType(MessagePackSerializer):
        grok.provides(ISerializer)
        grok.name(MessagePackSerializer.content_type)

except ImportError:
    pass


try:
    try:
        import json
        json  # pyflakes
    except ImportError:
        import simplejson as json

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
