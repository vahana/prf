import uuid
from marshmallow import Schema, fields
from prf.utils import dictset, issequence
import prf.exc


class UUIDType(fields.UUID):

    """This class makes sure UUID passed as objects are str'd"""

    def _deserialize(self, value):
        return super(UUIDType, self)._deserialize(value=str(value))


class BaseSchema(Schema):

    _model = None

    def make_object(self, data):
        return self._model(**data)


class DynamicSchema(object):
    def __init__(self, **kw):
        self.only = []
        self.exclude = []
        self.__dict__.update(kw)

    def dump(self, objs):
        fields = self.only + ['-%s'%each for each in self.exclude]

        try:
            if self.many:
                objs = [each.to_dict(fields) for each in objs]
            else:
                objs = objs.to_dict(fields)

            return dictset(data=objs)
        except AttributeError as e:
            raise prf.exc.HTTPBadRequest('%s can not be serialized: %s. Make sure to set `show_returns_many=True`' %\
                         ('Collection' if self.many else 'Resource', e))


@BaseSchema.error_handler
def handle_errors(schema, errors, obj):
    raise prf.exc.HTTPBadRequest(errors,
                                 extra={'model': schema._model.__name__})
