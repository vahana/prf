import json
import logging
import urllib
from pyramid.request import Request
from pyramid.response import Response

from prf.json_httpexceptions import *
from prf.utils import dictset, issequence, prep_params, process_fields
from prf import wrappers
from prf.resource import Action

log = logging.getLogger(__name__)


class ViewMapper(object):

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __call__(self, view):
        action_name = self.kwargs['attr']

        def view_mapper_wrapper(context, request):
            matchdict = request.matchdict.copy()
            matchdict.pop('action', None)
            matchdict.pop('traverse', None)

            view_obj = view(context, request)
            action = getattr(view_obj, action_name)

            resp = action(**matchdict)

            if isinstance(resp, Response):
                return resp

            elif action_name == Action.INDEX:
                return wrappers.add_meta(request, resp)

            # elif action_name == Action.SHOW:
            #     return resp

            elif action_name == Action.CREATE:
                return wrappers.wrap_in_http_created(request, resp)

            elif action_name in [Action.UPDATE, Action.DELETE]:
                return wrappers.wrap_in_http_ok(request, resp)

            return resp

        return view_mapper_wrapper


class BaseView(object):

    __view_mapper__ = ViewMapper
    _default_renderer = 'json'
    _serializer = None
    _acl = None

    def __init__(self, context, request, _params={}):
        self.context = context
        self.request = request
        self._model_class = None

        self._params = dictset(_params or request.params.mixed())
        ctype = request.content_type
        if request.method in ['POST', 'PUT', 'PATCH']:
            if ctype == 'application/json':
                try:
                    self._params.update(request.json)
                except ValueError, e:
                    log.error("Excpeting JSON. Received: '%s'. Request: %s %s"
                              , request.body, request.method, request.url)

        # no accept headers, use default
        if '' in request.accept:
            request.override_renderer = self._default_renderer
        elif 'application/json' in request.accept:

            request.override_renderer = 'prf_json'
        elif 'text/plain' in request.accept:

            request.override_renderer = 'string'


    def __getattr__(self, attr):
        if attr in [
            'index',
            'show',
            'create',
            'update',
            'delete',
            'update_many',
            'delete_many',
            ]:
            return self.not_allowed_action

        raise AttributeError(attr)

    def serialize(self, objs, many=False):
        if not self._serializer:
            return objs

        kw = {}
        fields = self._params.get('_fields')

        if fields is not None:
            kw['only'], kw['exclude'] = process_fields(fields)

        return self._serializer(many=many, strict=True, **kw).\
                                dump(objs).data

    def _index(self, **kw):
        objs = self.index(**kw)
        serielized = self.serialize(objs, many=True)

        count = len(serielized)
        total = getattr(objs, '_total', count)

        dict_ = dict(
            total = total,
            count = count,
            data = serielized
        )
        return dict_

    def _show(self, **kw):
        obj = self.show(**kw)

        if isinstance(obj, dict):
            fields = self._params.get('_fields')
            return dictset(obj).subset(fields) if fields else objs

        return self.serialize(obj, many=False)

    def _create(self, **kw):
        obj = self.create(**kw)
        if not obj:
            return None

        assert self._serializer
        return self._serializer().dump(obj).data

    def _update(self, **kw):
        return self.update(**kw)

    def _delete(self, **kw):
        return self.delete(**kw)

    def _update_many(self, **kw):
        return self.update_many(**kw)

    def _delete_many(self, **kw):
        return self.delete_many(**kw)

    def not_allowed_action(self, *a, **k):
        raise JHTTPMethodNotAllowed()

    def subrequest(self, url, params={}, method='GET'):
        req = Request.blank(url, cookies=self.request.cookies,
                            content_type='application/json', method=method)

        if req.method == 'GET' and params:
            req.body = urllib.urlencode(params)

        if req.method == 'POST':
            req.body = json.dumps(params)

        return self.request.invoke_subrequest(req)

    def needs_confirmation(self):
        return '__confirmation' not in self._params

    def delete_many(self, **kw):
        if not self._model_class:
            log.error('%s _model_class in invalid: %s',
                      self.__class__.__name__, self._model_class)
            raise JHTTPBadRequest

        objs = self._model_class.get_collection(**self._params)

        if self.needs_confirmation():
            return objs

        count = len(objs)
        objs.delete()
        return JHTTPOk('Deleted %s %s objects' % (count,
                       self._model_class.__name__))


class NoOp(BaseView):

    """Use this class as a stub if you want to layout all your resources before
    implementing actual views.
    """

    def index(self, **kw):
        return [dict(route=self.request.matched_route.name, kw=kw,
                params=self._params)]

    def show(self, **kw):
        return kw
