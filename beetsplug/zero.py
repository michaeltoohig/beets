# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Blemjhoo Tezoulbr <baobab@heresiarch.info>.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

""" Clears tag fields in media files."""

from __future__ import division, absolute_import, print_function
import six

import re

from beets.plugins import BeetsPlugin
from beets.mediafile import MediaFile
from beets.importer import action
from beets.util import confit

__author__ = 'baobab@heresiarch.info'
__version__ = '0.10'


class ZeroPlugin(BeetsPlugin):
    def __init__(self):
        super(ZeroPlugin, self).__init__()

        # Listeners.
        self.register_listener('write', self.write_event)
        self.register_listener('import_task_choice',
                               self.import_task_choice_event)

        self.config.add({
            'fields': [],
            'keep_fields': [],
            'update_database': False,
        })

        self.fields_to_progs = {}
        self.warned = False

        if self.config['fields'] and self.config['keep_fields']:
            self._log.warning(
                u'cannot blacklist and whitelist at the same time'
            )
        # Blacklist mode.
        elif self.config['fields']:
            for field in self.config['fields'].as_str_seq():
                self._set_pattern(field)
        # Whitelist mode.
        elif self.config['keep_fields']:
            for field in MediaFile.fields():
                if (field not in self.config['keep_fields'].as_str_seq() and
                        # These fields should always be preserved.
                        field not in ('id', 'path', 'album_id')):
                    self._set_pattern(field)

    def _set_pattern(self, field):
        """Set a field in `self.patterns` to a string list corresponding to
        the configuration, or `True` if the field has no specific
        configuration.
        """
        if field not in MediaFile.fields():
            self._log.error(u'invalid field: {0}', field)
        elif field in ('id', 'path', 'album_id'):
            self._log.warning(u'field \'{0}\' ignored, zeroing '
                              u'it would be dangerous', field)
        else:
            try:
                for pattern in self.config[field].as_str_seq():
                    prog = re.compile(pattern, re.IGNORECASE)
                    self.fields_to_progs.setdefault(field, []).append(prog)
            except confit.NotFoundError:
                # Matches everything
                self.fields_to_progs[field] = []

    def import_task_choice_event(self, session, task):
        """Listen for import_task_choice event."""
        if task.choice_flag == action.ASIS and not self.warned:
            self._log.warning(u'cannot zero in \"as-is\" mode')
            self.warned = True
        # TODO request write in as-is mode

    def write_event(self, item, path, tags):
        """Set values in tags to `None` if the key and value are matched
        by `self.patterns`.
        """
        if not self.fields_to_progs:
            self._log.warning(u'no fields, nothing to do')
            return

        for field, progs in self.fields_to_progs.items():
            if field in tags:
                value = tags[field]
                match = _match_progs(value, progs, self._log)
            else:
                value = ''
                match = not progs

            if match:
                self._log.debug(u'{0}: {1} -> None', field, value)
                tags[field] = None
                if self.config['update_database']:
                    item[field] = None


def _match_progs(value, progs, log):
    """Check if field (as string) is matching any of the patterns in
    the list.
    """
    if not progs:
        return True
    for prog in progs:
        if prog.search(six.text_type(value)):
            return True
    return False
