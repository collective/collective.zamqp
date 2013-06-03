# -*- coding: utf-8 -*-
import logging
import os


logger = logging.getLogger('collective.zamqp')

loglevels = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
}
loglevel = loglevels.get(os.environ.get('ZAMQP_LOGLEVEL'), logging.DEBUG)
