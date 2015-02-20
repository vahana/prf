from datetime import datetime
from prf.utils.utils import DKeyError, DValueError

def parametrize(func):

    def wrapper(dset, name, default=None, raise_on_empty=False, pop=False,
                **kw):

        if default is None:
            try:
                value = dset[name]
            except KeyError:
                raise DKeyError("Missing '%s'" % name)
        else:
            value = dset.get(name, default)

        if raise_on_empty and not value:
            raise DValueError("'%s' can not be empty" % name)

        result = func(dset, value, **kw)

        if pop:
            dset.pop(name, None)
        else:
            dset[name] = result

        return result

    return wrapper


@parametrize
def asbool(dset, value):
    truthy = frozenset(('t', 'true', 'y', 'yes', 'on', '1'))

    if value is None:
        return False
    if isinstance(value, bool):
        return value
    value = str(value).strip()
    return value.lower() in truthy


@parametrize
def aslist(dset, value, sep=',', remove_empty=True):
    _lst = (value if isinstance(value, list) else value.split(sep))
    return (filter(bool, _lst) if remove_empty else _lst)


@parametrize
def asint(dset, value):
    return int(value)


@parametrize
def asfloat(dset, value):
    return float(value)


def asdict(dset, name, _type=None, _set=False, pop=False):
    """
    Turn this 'a:2,b:blabla,c:True,a:'d' to {a:[2, 'd'], b:'blabla', c:True}

    """

    if _type is None:
        _type = lambda t: t

    dict_str = dset.pop(name, None)
    if not dict_str:
        return {}

    _dict = {}
    for item in split_strip(dict_str):
        key, _, val = item.partition(':')
        if key in _dict:
            if type(_dict[key]) is list:
                _dict[key].append(val)
            else:
                _dict[key] = [_dict[key], val]
        else:
            _dict[key] = _type(val)

    if _set:
        dset[name] = _dict
    elif pop:
        dset.pop(name, None)

    return _dict


def as_datetime(dset, name):
    if name in dset:
        try:
            dset[name] = datetime.strptime(dset[name], '%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            raise DValueError("Bad format for '%s' param. Must be ISO 8601, YYYY-MM-DDThh:mm:ssZ"
                              % name)

    return dset.get(name, None)