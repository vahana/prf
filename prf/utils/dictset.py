import urllib, re
from prf.utils.utils import DKeyError, DValueError, split_strip
from prf.utils.convert import *


def get_seg(d, path):
    for seg in path:
        d = d[seg]
    # if not isinstance(d, dict):
    #     raise ValueError(
    #         '`%s` must be (derived from) dict. Got `%s` instead' % (d, type(d)))

    return d


def merge(d1, d2, prefix_keys=None):
    """
    from prf.utils import dictset, merge
    d1 = dictset({'a':{'b':{'c':1}}})
    d2 = dictset({'a':{'b':{'d':1}}})
    merge(d1, d2)

    """
    prefix_keys = prefix_keys or []
    d1_ = get_seg(d1, prefix_keys)
    d2_ = get_seg(d2, prefix_keys)

    for key, val in d2_.items():
        if key not in d1_:
            d1_.update(d2_)
            return

        prefix_keys.append(key)
        merge(d1, d2, prefix_keys)


def expand_list(param):
    _new = []
    if isinstance(param, (list, set)):
        for each in param:
            if isinstance(each, basestring) and each.find(',') != -1:
                _new.extend(split_strip(each))
            elif isinstance(each, (list, set)):
                _new.extend(each)
            else:
                _new.append(each)
    elif isinstance(param, basestring) and param.find(',') != -1:

        _new = split_strip(param)

    return _new


def process_fields(fields):
    fields_only = []
    fields_exclude = []
    nested = {}
    show_as = {}

    if isinstance(fields, basestring):
        fields = split_strip(fields)

    for field in expand_list(fields):
        field = field.strip()
        if not field:
            continue
        if field[0] == '-':
            fields_exclude.append(field[1:])
        else:
            if '__as__' in field:
                key,_,val = field.partition('__as__')
                show_as[key] = val
                field = key

            if '.' in field:
                key = field.split('.')[0]
                nested[field] = key
                field = key

            fields_only.append(field)

    return dictset({
             'only': fields_only,
             'exclude':fields_exclude,
             'nested': nested,
             'show_as': show_as})


class dictset(dict):

    """Named dict, with some set functionalities

        dset = dictset(a=1,b={'c':1})
        dset.a == dset['a'] == 1
        dset.b.c == 1
        dset.subset(['a']) == {'a':1} == dset.subset('-b')

    """

    DKeyError = DKeyError
    DValueError = DValueError

    def __init__(self, *arg, **kw):
        super(dictset, self).__init__(*arg, **kw)
        self.to_dictset()

    def __getattr__(self, key):
        if key.startswith('__'): # dont touch the special attributes
            return super(dictset, self).__getattr__(key) #pragma nocoverage

        try:
            return self[key]
        except KeyError as e:
            raise DKeyError(e.message)

    def __setattr__(self, key, val):
        if isinstance(val, dict):
            val = dictset(val)
        self[key] = val

    def __delattr__(self, key):
        self.pop(key, None)

    def __contains__(self, item):
        if isinstance(item, (tuple, list, set)):
            return bool(set(self.keys()) & set(item))
        else:
            return super(dictset, self).__contains__(item)

    def __add__(self, item):
        return self.copy().update(item)

    def __iadd__(self, item):
        return self.update(item)

    def __getitem__(self, key):
        try:
            return super(dictset, self).__getitem__(key)
        except KeyError as e:
            raise DKeyError(e.message)

    def to_dictset(self):
        for key, val in self.items():
            if isinstance(val, dict):
                self[key] = dictset(val)
            if isinstance(val, list):
                new_list = []
                for each in val:
                    if isinstance(each, dict):
                        new_list.append(dictset(each))
                    else:
                        new_list.append(each)
                self[key] = new_list

        return self

    def copy(self):
        return dictset(super(dictset, self).copy())

    def subset(self, keys):
        only, exclude, nested = process_fields(keys).mget(['only','exclude', 'nested'])

        _d = dictset()

        if only and exclude:
            raise DValueError('Can only supply either positive or negative keys,'
                              ' but not both')

        if only or nested:
            _d = dictset([[k, v] for (k, v) in self.items() if k in only+nested.keys()])
        elif exclude:
            _d = dictset([[k, v] for (k, v) in self.items() if k
                           not in exclude])

        return _d

    def asbool(self, *arg, **kw):
        return asbool(self, *arg, **kw)

    def aslist(self, *arg, **kw):
        return aslist(self, *arg, **kw)

    def asset(self, *arg, **kw):
        return self.aslist(*arg, unique=True, **kw)

    def asint(self, *arg, **kw):
        return asint(self, *arg, **kw)

    def asfloat(self, *arg, **kw):
        return asfloat(self, *arg, **kw)

    def asdict(self, *arg, **kw):
        return asdict(self, *arg, **kw)

    def as_datetime(self, *arg, **kw):
        return as_datetime(self, *arg, **kw)

    def asstr(self, *arg, **kw):
        return asstr(self, *arg, **kw)

    def asrange(self, *arg, **kw):
        return asrange(self, *arg, **kw)

    def remove(self, keys):
        for k in keys:
            self.pop(k, None)

    def update(self, d_):
        super(dictset, self).update(dictset(d_))
        return self

    def merge(self, d_):
        merge(self, d_)
        return self

    def pop_by_values(self, vals):
        if not isinstance(vals, list):
            vals = [vals]

        for k, v in self.items():
            if v in vals:
                self.pop(k)
        return self

    def get_tree(self, prefix, defaults={}, sep='.'):
        if prefix[-1] != '.':
            prefix += sep

        _dict = dictset(defaults)
        for key, val in self.items():
            if key.startswith(prefix):
                _k = key.partition(prefix)[-1]
                _dict[_k] = val
        return _dict

    def mget(self, keys):
        return [self[e] for e in split_strip(keys) if e in self]

    @classmethod
    def from_dotted(cls, dotkey, val):
        # 'a.b.c', 100 -> {a:{b:{c:100}}}
        # 'a.b.1', 100 -> {a:{b:[None,100]}}

        key, _, sufix = dotkey.partition('.')

        if not sufix:
            if key.isdigit():
                _lst = [None]*int(key) + [val]
                return _lst
            else:
                return cls({key:val})

        if key.isdigit():
            _lst = [None]*int(key) + [cls.from_dotted(sufix, val)]
            return _lst
        else:
            return cls({key: cls.from_dotted(sufix, val)})

    def has(self, keys, check_type=basestring, allow_empty=False,
                        err='', _all=True, allow_missing=False,
                        allowed_values=[]):
        errors = []

        if isinstance(keys, basestring):
            keys = [keys]

        self_flat = self.flat().update(self) # update with self to include high level keys too

        for key in keys:
            if key in self_flat:
                if check_type and not isinstance(self_flat[key], check_type):
                    errors.append(err or '`%s` must be type `%s`, got `%s`'\
                                          % (key, check_type, type(self_flat[key])))

                if allowed_values and self_flat[key] not in allowed_values:
                    errors.append(err or '`%s` allowed values are: %s, got: `%s`'\
                                          % (key, allowed_values, self_flat[key]))

            elif not allow_missing:
                if allowed_values:
                    err = 'Missing key or invalid values: `%s`. Allowed values are: %s'\
                                          % (key, allowed_values)
                errors.append(err or 'Missing key: `%s`' % key)

        if (errors and _all) or (not _all and len(errors) >= len(keys)):
            raise DValueError(str(errors))

        return True

    def transform(self, rules):
        _d = dictset()

        flat_dict = self.flat()
        flat_rules = rules.flat()
        # flat_dict.update(self)

        for path, val in flat_dict.items():
            if path in rules:
                _d.merge(dictset.from_dotted(rules[path], val))

        return _d

    @classmethod
    def build_from(cls, source, rules, allow_empty=True,
                    allow_missing=False, inverse=False):
        _d = dictset()

        flat_rules = dictset(rules).flat()
        flat_source = dictset(source).flat()
        flat_source.update(source)

        for key, val in flat_rules.items():
            if not val: # if val in the rule is missing, use the key
                val = key

            if inverse:
                key,val = val,key # flip em

            if key.endswith('.'):
                _val = flat_source.get_treet(key)
            else:
                if allow_missing:
                    _val = flat_source.get(key, key)
                else:
                    _val = flat_source[key]

            if _val != "" or allow_empty:
                _d[val] = _val

        return _d.unflat()

    def flat(self):
        return dictset(dict_to_args(self))

    def unflat(self):
        return dictset(args_to_dict(self))

    def set_default(self, name, val):
        if name not in self.flat():
            self.merge(dictset.from_dotted(name, val))
        return val


#based on jsonurl

def type_cast(value):
    return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def list_to_args(l):
    args = dictset()
    pos = 0
    for i in l:
        if isinstance(i, dict):
            sub = dict_to_args(i)
            for s, nv in sub.items():
                args[str(pos) + "." + s] = nv
        elif isinstance(i, list):
            sub = list_to_args(i)
            for s, nv in sub.items():
                args[str(pos) + "." + s] = nv
        else:
            args[str(pos)] = i
        pos += 1
    return args


def dict_to_args(d):
    args = dictset()
    for k, v in d.items():
        if isinstance(v, dict):
            sub = dict_to_args(v)
            for s, nv in sub.items():
                args["%s.%s" % (k,s)] = nv
        elif isinstance(v, list):
            sub = list_to_args(v)
            for s, nv in sub.items():
                args["%s.%s" % (k,s)] = nv
        else:
            args[k] = v
    return args


def dot_split(s):
    return [part for part in re.split("(?<!\.)\.(?!\.)", s)]


def args_to_dict(args):
    d = dictset()
    keys = args.keys()
    keys.sort()

    for arg in keys:
        value = args[arg]

        bits = dot_split(arg)
        ctx = d

        for i in range(len(bits)):
            bit = bits[i]
            last = not (i < len(bits) - 1)

            next_is_dict = False
            if not last:
                try:
                    int(bits[i + 1])
                except ValueError:
                    next_is_dict = True

            if isinstance(ctx, dict):
                if not ctx.has_key(bit):
                    if not last:
                        ctx[bit] = dictset() if next_is_dict else []
                        ctx = ctx[bit]
                    else:
                        ctx[bit] = type_cast(value)
                        ctx = None
                else:
                    ctx = ctx[bit]
            elif isinstance(ctx, list):
                if not last:
                    if int(bit) > len(ctx) - 1:
                        ctx.append(dictset() if next_is_dict else [])
                    try:
                        ctx = ctx[int(bit)]
                    except IndexError as e:
                        pass
                else:
                    ctx.append(type_cast(value))
                    ctx = None
    return d
