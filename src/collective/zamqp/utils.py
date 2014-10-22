# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyright (c) 2012 University of Jyväskylä and Contributors.
###
"""Helpers for re-using amqp-supporting packages between different buildouts"""

import logging
import os
from App.config import getConfiguration


def getBuildoutName():
    cfg = getConfiguration()
    # under a buildout environment cfg.instancehome is usually something like
    # '/var/buildouts/buildout_name/parts/instance'
    parts = getattr(cfg, 'instancehome', '').split('/')
    if len(parts) > 2:
        return parts[-3]
    else:
        # configuration not found, return some sane default string
        return 'collective.zamqp.default'


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
