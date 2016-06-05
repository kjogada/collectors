# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import uuid
import scrapy
import logging
from datetime import datetime
from abc import abstractmethod
from . import fields
logger = logging.getLogger(__name__)


# Module API

class Record(scrapy.Item):

    # Public

    def __repr__(self):
        template = '<%s: %s>'
        text = template % (self.table.upper(), self.get(self.primary_key))
        return text

    @classmethod
    def create(cls, source, data):

        # Init dict
        self = cls()

        # We could sync naming here with database
        # created_at/updated_at etc

        # Add metadata
        ident = uuid.uuid4().hex
        timestamp = datetime.utcnow()
        self.fields['meta_id'] = fields.Text()
        self.fields['meta_source'] = fields.Text()
        self.fields['meta_created'] = fields.Datetime()
        self.fields['meta_updated'] = fields.Datetime()
        self['meta_id'] = ident
        self['meta_source'] = source
        self['meta_created'] = timestamp
        self['meta_updated'] = timestamp

        # Add data
        undefined = []
        for key, value in data.items():
            field = self.fields.get(key)
            if field is None:
                undefined.append(key)
                continue
            if value is None:
                continue
            try:
                value = field.parse(value)
            except Exception as exception:
                message = 'Parsing error: %s=%s: %s'
                message = message % (key, value, exception)
                logger.exception(message)
                continue
            self[key] = value
        for key in undefined:
            logger.warning('Undefined field: %s - %s' % (self, key))

        return self

    @property
    @abstractmethod
    def table(self):
        """Source name.
        """
        pass  # pragma: no cover

    # We could move responsibility of defining
    # primary/updated key to Field object like in sqlalchemy

    @property
    @abstractmethod
    def primary_key(self):
        """Item primary key.
        """
        pass  # pragma: no cover

    @property
    @abstractmethod
    def ensure_fields(self):
        """Item updated key.
        """
        pass  # pragma: no cover

    @property
    def types(self):
        """Item types.
        """
        types = {}
        for key, field in self.fields.items():
            types[key] = field.type
        return types

    def write(self, conn):
        """Write record to warehouse.

        Args:
            conn (dict): connections dictionary

        """
        table = conn['warehouse'].get_table(
                self.table,
                primary_id=self.primary_key,
                primary_type='String')
        action = 'created'
        if table.find_one(**{self.primary_key: self[self.primary_key]}):
            action = 'updated'
            for key in ['meta_id', 'meta_updated']:
                del self[key]
        try:
            table.upsert(
                self, [self.primary_key],
                ensure=self.ensure_fields, types=self.types)
        except Exception as exception:
            logger.exception('Saving error: %s: %s' % (self, repr(exception)))
        else:
            logger.debug('Record - %s: %s - %s fields', action, self, len(self))
