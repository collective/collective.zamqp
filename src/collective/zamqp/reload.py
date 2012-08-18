# -*- coding: utf-8 -*-
###
# collective.zamqp
#
# Licensed under the ZPL license, see LICENCE.txt for more details.
#
# Copyright (c) 2012 University of Jyväskylä and Contributors.
###
"""sauna.reload-support"""

from collective.zamqp.connection import connect_all as connect_all

from sauna.reload import reload_paths


def connect_all_with_reload(self):
    """Connect all IBrokerConnections when sauna.reload is enabled"""
    if reload_paths:
        connect_all()


def connect_all_without_reload(self):
    """Connect all IBrokerConnections when sauna.reload is disabled"""
    if not reload_paths:
        connect_all()
