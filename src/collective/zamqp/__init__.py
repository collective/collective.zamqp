# -*- coding: utf-8 -*-
import logging
import os


class Logger(object):

    def __init__(self, name, default_level):
        self.logger = logging.getLogger(name)
        self.default_level = default_level

    def default(self, message, *args, **kwargs):
        self.logger.log(self.default_level, message, *args, **kwargs)

    def __getattr__(self, item):
        return getattr(self.logger, item)


logger = Logger('collective.zamqp', default_level={
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
}.get(os.environ.get('ZAMQP_LOGLEVEL'), logging.DEBUG))

