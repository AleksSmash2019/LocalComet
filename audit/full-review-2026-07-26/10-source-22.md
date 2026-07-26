# Полный исходный код (продолжение)

### ПУТЬ: Python/pythoncore-3.14-64/Lib/enum.py (2169 строк, 87619 байт)

````python
import sys
import builtins as bltns
from types import MappingProxyType, DynamicClassAttribute


__all__ = [
        'EnumType', 'EnumMeta', 'EnumDict',
        'Enum', 'IntEnum', 'StrEnum', 'Flag', 'IntFlag', 'ReprEnum',
        'auto', 'unique', 'property', 'verify', 'member', 'nonmember',
        'FlagBoundary', 'STRICT', 'CONFORM', 'EJECT', 'KEEP',
        'global_flag_repr', 'global_enum_repr', 'global_str', 'global_enum',
        'EnumCheck', 'CONTINUOUS', 'NAMED_FLAGS', 'UNIQUE',
        'pickle_by_global_name', 'pickle_by_enum_name',
        ]


# Dummy value for Enum and Flag as there are explicit checks for them
# before they have been created.
# This is also why there are checks in EnumType like `if Enum is not None`
Enum = Flag = EJECT = _stdlib_enums = ReprEnum = None

class nonmember(object):
    """
    Protects item from becoming an Enum member during class creation.
    """
    def __init__(self, value):
        self.value = value

class member(object):
    """
    Forces item to become an Enum member during class creation.
    """
    def __init__(self, value):
        self.value = value

def _is_descriptor(obj):
    """
    Returns True if obj is a descriptor, False otherwise.
    """
    return (
            hasattr(obj, '__get__') or
            hasattr(obj, '__set__') or
            hasattr(obj, '__delete__')
            )

def _is_dunder(name):
    """
    Returns True if a __dunder__ name, False otherwise.
    """
    return (
            len(name) > 4 and
            name[:2] == name[-2:] == '__' and
            name[2] != '_' and
            name[-3] != '_'
            )

def _is_sunder(name):
    """
    Returns True if a _sunder_ name, False otherwise.
    """
    return (
            len(name) > 2 and
            name[0] == name[-1] == '_' and
            name[1] != '_' and
            name[-2] != '_'
            )

def _is_internal_class(cls_name, obj):
    # do not use `re` as `re` imports `enum`
    if not isinstance(obj, type):
        return False
    qualname = getattr(obj, '__qualname__', '')
    s_pattern = cls_name + '.' + getattr(obj, '__name__', '')
    e_pattern = '.' + s_pattern
    return qualname == s_pattern or qualname.endswith(e_pattern)

def _is_private(cls_name, name):
    # do not use `re` as `re` imports `enum`
    pattern = '_%s__' % (cls_name, )
    pat_len = len(pattern)
    if (
            len(name) > pat_len
            and name.startswith(pattern)
            and (name[-1] != '_' or name[-2] != '_')
        ):
        return True
    else:
        return False

def _is_single_bit(num):
    """
    True if only one bit set in num (should be an int)
    """
    if num == 0:
        return False
    num &= num - 1
    return num == 0

def _make_class_unpicklable(obj):
    """
    Make the given obj un-picklable.

    obj should be either a dictionary, or an Enum
    """
    def _break_on_call_reduce(self, proto):
        raise TypeError('%r cannot be pickled' % self)
    if isinstance(obj, dict):
        obj['__reduce_ex__'] = _break_on_call_reduce
        obj['__module__'] = '<unknown>'
    else:
        setattr(obj, '__reduce_ex__', _break_on_call_reduce)
        setattr(obj, '__module__', '<unknown>')

def _iter_bits_lsb(num):
    # num must be a positive integer
    original = num
    if isinstance(num, Enum):
        num = num.value
    if num < 0:
        raise ValueError('%r is not a positive integer' % original)
    while num:
        b = num & (~num + 1)
        yield b
        num ^= b

def show_flag_values(value):
    return list(_iter_bits_lsb(value))

def bin(num, max_bits=None):
    """
    Like built-in bin(), except negative values are represented in
    twos-complement, and the leading bit always indicates sign
    (0=positive, 1=negative).

    >>> bin(10)
    '0b0 1010'
    >>> bin(~10)   # ~10 is -11
    '0b1 0101'
    """

    num = num.__index__()
    ceiling = 2 ** (num).bit_length()
    if num >= 0:
        s = bltns.bin(num + ceiling).replace('1', '0', 1)
    else:
        s = bltns.bin(~num ^ (ceiling - 1) + ceiling)
    sign = s[:3]
    digits = s[3:]
    if max_bits is not None:
        if len(digits) < max_bits:
            digits = (sign[-1] * max_bits + digits)[-max_bits:]
    return "%s %s" % (sign, digits)

class _not_given:
    def __repr__(self):
        return('<not given>')
_not_given = _not_given()

class _auto_null:
    def __repr__(self):
        return '_auto_null'
_auto_null = _auto_null()

class auto:
    """
    Instances are replaced with an appropriate value in Enum class suites.
    """
    def __init__(self, value=_auto_null):
        self.value = value

    def __repr__(self):
        return "auto(%r)" % self.value

class property(DynamicClassAttribute):
    """
    This is a descriptor, used to define attributes that act differently
    when accessed through an enum member and through an enum class.
    Instance access is the same as property(), but access to an attribute
    through the enum class will instead look in the class' _member_map_ for
    a corresponding enum member.
    """

    member = None
    _attr_type = None
    _cls_type = None

    def __get__(self, instance, ownerclass=None):
        if instance is None:
            if self.member is not None:
                return self.member
            else:
                raise AttributeError(
                        '%r has no attribute %r' % (ownerclass, self.name)
                        )
        if self.fget is not None:
            # use previous enum.property
            return self.fget(instance)
        elif self._attr_type == 'attr':
            # look up previous attribute
            return getattr(self._cls_type, self.name)
        elif self._attr_type == 'desc':
            # use previous descriptor
            return getattr(instance._value_, self.name)
        # look for a member by this name.
        try:
            return ownerclass._member_map_[self.name]
        except KeyError:
            raise AttributeError(
                    '%r has no attribute %r' % (ownerclass, self.name)
                    ) from None

    def __set__(self, instance, value):
        if self.fset is not None:
            return self.fset(instance, value)
        raise AttributeError(
                "<enum %r> cannot set attribute %r" % (self.clsname, self.name)
                )

    def __delete__(self, instance):
        if self.fdel is not None:
            return self.fdel(instance)
        raise AttributeError(
                "<enum %r> cannot delete attribute %r" % (self.clsname, self.name)
                )

    def __set_name__(self, ownerclass, name):
        self.name = name
        self.clsname = ownerclass.__name__


class _proto_member:
    """
    intermediate step for enum members between class execution and final creation
    """

    def __init__(self, value):
        self.value = value

    def __set_name__(self, enum_class, member_name):
        """
        convert each quasi-member into an instance of the new enum class
        """
        # first step: remove ourself from enum_class
        delattr(enum_class, member_name)
        # second step: create member based on enum_class
        value = self.value
        if not isinstance(value, tuple):
            args = (value, )
        else:
            args = value
        if enum_class._member_type_ is tuple:   # special case for tuple enums
            args = (args, )     # wrap it one more time
        if not enum_class._use_args_:
            enum_member = enum_class._new_member_(enum_class)
        else:
            enum_member = enum_class._new_member_(enum_class, *args)
        if not hasattr(enum_member, '_value_'):
            if enum_class._member_type_ is object:
                enum_member._value_ = value
            else:
                try:
                    enum_member._value_ = enum_class._member_type_(*args)
                except Exception as exc:
                    new_exc = TypeError(
                            '_value_ not set in __new__, unable to create it'
                            )
                    new_exc.__cause__ = exc
                    raise new_exc
        value = enum_member._value_
        enum_member._name_ = member_name
        enum_member.__objclass__ = enum_class
        enum_member.__init__(*args)
        enum_member._sort_order_ = len(enum_class._member_names_)

        if Flag is not None and issubclass(enum_class, Flag):
            if isinstance(value, int):
                enum_class._flag_mask_ |= value
                if _is_single_bit(value):
                    enum_class._singles_mask_ |= value
            enum_class._all_bits_ = 2 ** ((enum_class._flag_mask_).bit_length()) - 1

        # If another member with the same value was already defined, the
        # new member becomes an alias to the existing one.
        try:
            try:
                # try to do a fast lookup to avoid the quadratic loop
                enum_member = enum_class._value2member_map_[value]
            except TypeError:
                for name, canonical_member in enum_class._member_map_.items():
                    if canonical_member._value_ == value:
                        enum_member = canonical_member
                        break
                else:
                    raise KeyError
        except KeyError:
            # this could still be an alias if the value is multi-bit and the
            # class is a flag class
            if (
                    Flag is None
                    or not issubclass(enum_class, Flag)
                ):
                # no other instances found, record this member in _member_names_
                enum_class._member_names_.append(member_name)
            elif (
                    Flag is not None
                    and issubclass(enum_class, Flag)
                    and isinstance(value, int)
                    and _is_single_bit(value)
                ):
                # no other instances found, record this member in _member_names_
                enum_class._member_names_.append(member_name)

        enum_class._add_member_(member_name, enum_member)
        try:
            # This may fail if value is not hashable. We can't add the value
            # to the map, and by-value lookups for this value will be
            # linear.
            enum_class._value2member_map_.setdefault(value, enum_member)
            if value not in enum_class._hashable_values_:
                enum_class._hashable_values_.append(value)
        except TypeError:
            # keep track of the value in a list so containment checks are quick
            enum_class._unhashable_values_.append(value)
            enum_class._unhashable_values_map_.setdefault(member_name, []).append(value)


class EnumDict(dict):
    """
    Track enum member order and ensure member names are not reused.

    EnumType will use the names found in self._member_names as the
    enumeration member names.
    """
    def __init__(self, cls_name=None):
        super().__init__()
        self._member_names = {} # use a dict -- faster look-up than a list, and keeps insertion order since 3.7
        self._last_values = []
        self._ignore = []
        self._auto_called = False
        self._cls_name = cls_name

    def __setitem__(self, key, value):
        """
        Changes anything not dundered or not a descriptor.

        If an enum member name is used twice, an error is raised; duplicate
        values are not checked for.

        Single underscore (sunder) names are reserved.
        """
        if self._cls_name is not None and _is_private(self._cls_name, key):
            # do nothing, name will be a normal attribute
            pass
        elif _is_sunder(key):
            if key not in (
                    '_order_',
                    '_generate_next_value_', '_numeric_repr_', '_missing_', '_ignore_',
                    '_iter_member_', '_iter_member_by_value_', '_iter_member_by_def_',
                    '_add_alias_', '_add_value_alias_',
                    # While not in use internally, those are common for pretty
                    # printing and thus excluded from Enum's reservation of
                    # _sunder_ names
                    ) and not key.startswith('_repr_'):
                raise ValueError(
                        '_sunder_ names, such as %r, are reserved for future Enum use'
                        % (key, )
                        )
            if key == '_generate_next_value_':
                # check if members already defined as auto()
                if self._auto_called:
                    raise TypeError("_generate_next_value_ must be defined before members")
                _gnv = value.__func__ if isinstance(value, staticmethod) else value
                setattr(self, '_generate_next_value', _gnv)
            elif key == '_ignore_':
                if isinstance(value, str):
                    value = value.replace(',',' ').split()
                else:
                    value = list(value)
                self._ignore = value
                already = set(value) & set(self._member_names)
                if already:
                    raise ValueError(
                            '_ignore_ cannot specify already set names: %r'
                            % (already, )
                            )
        elif _is_dunder(key):
            if key == '__order__':
                key = '_order_'
        elif key in self._member_names:
            # descriptor overwriting an enum?
            raise TypeError('%r already defined as %r' % (key, self[key]))
        elif key in self._ignore:
            pass
        elif isinstance(value, nonmember):
            # unwrap value here; it won't be processed by the below `else`
            value = value.value
        elif _is_descriptor(value):
            pass
        elif self._cls_name is not None and _is_internal_class(self._cls_name, value):
            # do nothing, name will be a normal attribute
            pass
        else:
            if key in self:
                # enum overwriting a descriptor?
                raise TypeError('%r already defined as %r' % (key, self[key]))
            elif isinstance(value, member):
                # unwrap value here -- it will become a member
                value = value.value
            non_auto_store = True
            single = False
            if isinstance(value, auto):
                single = True
                value = (value, )
            if isinstance(value, tuple) and any(isinstance(v, auto) for v in value):
                # insist on an actual tuple, no subclasses, in keeping with only supporting
                # top-level auto() usage (not contained in any other data structure)
                auto_valued = []
                t = type(value)
                for v in value:
                    if isinstance(v, auto):
                        non_auto_store = False
                        if v.value == _auto_null:
                            v.value = self._generate_next_value(
                                    key, 1, len(self._member_names), self._last_values[:],
                                    )
                            self._auto_called = True
                        v = v.value
                        self._last_values.append(v)
                    auto_valued.append(v)
                if single:
                    value = auto_valued[0]
                else:
                    try:
                        # accepts iterable as multiple arguments?
                        value = t(auto_valued)
                    except TypeError:
                        # then pass them in singly
                        value = t(*auto_valued)
            self._member_names[key] = None
            if non_auto_store:
                self._last_values.append(value)
        super().__setitem__(key, value)

    @property
    def member_names(self):
        return list(self._member_names)

    def update(self, members, **more_members):
        try:
            for name in members.keys():
                self[name] = members[name]
        except AttributeError:
            for name, value in members:
                self[name] = value
        for name, value in more_members.items():
            self[name] = value

_EnumDict = EnumDict        # keep private name for backwards compatibility


class EnumType(type):
    """
    Metaclass for Enum
    """

    @classmethod
    def __prepare__(metacls, cls, bases, **kwds):
        # check that previous enum members do not exist
        metacls._check_for_existing_members_(cls, bases)
        # create the namespace dict
        enum_dict = EnumDict(cls)
        # inherit previous flags and _generate_next_value_ function
        member_type, first_enum = metacls._get_mixins_(cls, bases)
        if first_enum is not None:
            enum_dict['_generate_next_value_'] = getattr(
                    first_enum, '_generate_next_value_', None,
                    )
        return enum_dict

    def __new__(metacls, cls, bases, classdict, *, boundary=None, _simple=False, **kwds):
        # an Enum class is final once enumeration items have been defined; it
        # cannot be mixed with other types (int, float, etc.) if it has an
        # inherited __new__ unless a new __new__ is defined (or the resulting
        # class will fail).
        #
        if _simple:
            return super().__new__(metacls, cls, bases, classdict, **kwds)
        #
        # remove any keys listed in _ignore_
        classdict.setdefault('_ignore_', []).append('_ignore_')
        ignore = classdict['_ignore_']
        for key in ignore:
            classdict.pop(key, None)
        #
        # grab member names
        member_names = classdict._member_names
        #
        # check for illegal enum names (any others?)
        invalid_names = set(member_names) & {'mro', ''}
        if invalid_names:
            raise ValueError('invalid enum member name(s) %s'  % (
                    ','.join(repr(n) for n in invalid_names)
                    ))
        #
        # adjust the sunders
        _order_ = classdict.pop('_order_', None)
        _gnv = classdict.get('_generate_next_value_')
        if _gnv is not None and type(_gnv) is not staticmethod:
            _gnv = staticmethod(_gnv)
        # convert to normal dict
        classdict = dict(classdict.items())
        if _gnv is not None:
            classdict['_generate_next_value_'] = _gnv
        #
        # data type of member and the controlling Enum class
        member_type, first_enum = metacls._get_mixins_(cls, bases)
        __new__, save_new, use_args = metacls._find_new_(
                classdict, member_type, first_enum,
                )
        classdict['_new_member_'] = __new__
        classdict['_use_args_'] = use_args
        #
        # convert future enum members into temporary _proto_members
        for name in member_names:
            value = classdict[name]
            classdict[name] = _proto_member(value)
        #
        # house-keeping structures
        classdict['_member_names_'] = []
        classdict['_member_map_'] = {}
        classdict['_value2member_map_'] = {}
        classdict['_hashable_values_'] = []          # for comparing with non-hashable types
        classdict['_unhashable_values_'] = []       # e.g. frozenset() with set()
        classdict['_unhashable_values_map_'] = {}
        classdict['_member_type_'] = member_type
        # now set the __repr__ for the value
        classdict['_value_repr_'] = metacls._find_data_repr_(cls, bases)
        #
        # Flag structures (will be removed if final class is not a Flag
        classdict['_boundary_'] = (
                boundary
                or getattr(first_enum, '_boundary_', None)
                )
        classdict['_flag_mask_'] = 0
        classdict['_singles_mask_'] = 0
        classdict['_all_bits_'] = 0
        classdict['_inverted_'] = None
        try:
            classdict['_%s__in_progress' % cls] = True
            enum_class = super().__new__(metacls, cls, bases, classdict, **kwds)
            classdict['_%s__in_progress' % cls] = False
            delattr(enum_class, '_%s__in_progress' % cls)
        except Exception as e:
            # since 3.12 the note "Error calling __set_name__ on '_proto_member' instance ..."
            # is tacked on to the error instead of raising a RuntimeError, so discard it
            if hasattr(e, '__notes__'):
                del e.__notes__
            raise
        # update classdict with any changes made by __init_subclass__
        classdict.update(enum_class.__dict__)
        #
        # double check that repr and friends are not the mixin's or various
        # things break (such as pickle)
        # however, if the method is defined in the Enum itself, don't replace
        # it
        #
        # Also, special handling for ReprEnum
        if ReprEnum is not None and ReprEnum in bases:
            if member_type is object:
                raise TypeError(
                        'ReprEnum subclasses must be mixed with a data type (i.e.'
                        ' int, str, float, etc.)'
                        )
            if '__format__' not in classdict:
                enum_class.__format__ = member_type.__format__
                classdict['__format__'] = enum_class.__format__
            if '__str__' not in classdict:
                method = member_type.__str__
                if method is object.__str__:
                    # if member_type does not define __str__, object.__str__ will use
                    # its __repr__ instead, so we'll also use its __repr__
                    method = member_type.__repr__
                enum_class.__str__ = method
                classdict['__str__'] = enum_class.__str__
        for name in ('__repr__', '__str__', '__format__', '__reduce_ex__'):
            if name not in classdict:
                # check for mixin overrides before replacing
                enum_method = getattr(first_enum, name)
                found_method = getattr(enum_class, name)
                object_method = getattr(object, name)
                data_type_method = getattr(member_type, name)
                if found_method in (data_type_method, object_method):
                    setattr(enum_class, name, enum_method)
        #
        # for Flag, add __or__, __and__, __xor__, and __invert__
        if Flag is not None and issubclass(enum_class, Flag):
            for name in (
                    '__or__', '__and__', '__xor__',
                    '__ror__', '__rand__', '__rxor__',
                    '__invert__'
                ):
                if name not in classdict:
                    enum_method = getattr(Flag, name)
                    setattr(enum_class, name, enum_method)
                    classdict[name] = enum_method
        #
        # replace any other __new__ with our own (as long as Enum is not None,
        # anyway) -- again, this is to support pickle
        if Enum is not None:
            # if the user defined their own __new__, save it before it gets
            # clobbered in case they subclass later
            if save_new:
                enum_class.__new_member__ = __new__
            enum_class.__new__ = Enum.__new__
        #
        # py3 support for definition order (helps keep py2/py3 code in sync)
        #
        # _order_ checking is spread out into three/four steps
        # - if enum_class is a Flag:
        #   - remove any non-single-bit flags from _order_
        # - remove any aliases from _order_
        # - check that _order_ and _member_names_ match
        #
        # step 1: ensure we have a list
        if _order_ is not None:
            if isinstance(_order_, str):
                _order_ = _order_.replace(',', ' ').split()
        #
        # remove Flag structures if final class is not a Flag
        if (
                Flag is None and cls != 'Flag'
                or Flag is not None and not issubclass(enum_class, Flag)
            ):
            delattr(enum_class, '_boundary_')
            delattr(enum_class, '_flag_mask_')
            delattr(enum_class, '_singles_mask_')
            delattr(enum_class, '_all_bits_')
            delattr(enum_class, '_inverted_')
        elif Flag is not None and issubclass(enum_class, Flag):
            # set correct __iter__
            member_list = [m._value_ for m in enum_class]
            if member_list != sorted(member_list):
                enum_class._iter_member_ = enum_class._iter_member_by_def_
            if _order_:
                # _order_ step 2: remove any items from _order_ that are not single-bit
                _order_ = [
                        o
                        for o in _order_
                        if o not in enum_class._member_map_ or _is_single_bit(enum_class[o]._value_)
                        ]
        #
        if _order_:
            # _order_ step 3: remove aliases from _order_
            _order_ = [
                    o
                    for o in _order_
                    if (
                        o not in enum_class._member_map_
                        or
                        (o in enum_class._member_map_ and o in enum_class._member_names_)
                        )]
            # _order_ step 4: verify that _order_ and _member_names_ match
            if _order_ != enum_class._member_names_:
                raise TypeError(
                        'member order does not match _order_:\n  %r\n  %r'
                        % (enum_class._member_names_, _order_)
                        )
        #
        return enum_class

    def __bool__(cls):
        """
        classes/types should always be True.
        """
        return True

    def __call__(cls, value, names=_not_given, *values, module=None, qualname=None, type=None, start=1, boundary=None):
        """
        Either returns an existing member, or creates a new enum class.

        This method is used both when an enum class is given a value to
        match to an enumeration member (i.e. Color(3)) and for the
        functional API (i.e. Color = Enum('Color', names='RED GREEN BLUE')).

        The value lookup branch is chosen if the enum is final.

        When used for the functional API:

        `value` will be the name of the new class.

        `names` should be either a string of white-space/comma delimited
        names (values will start at `start`), or an iterator/mapping of
        name, value pairs.

        `module` should be set to the module this class is being created in;
        if it is not set, an attempt to find that module will be made, but
        if it fails the class will not be picklable.

        `qualname` should be set to the actual location this class can be
        found at in its module; by default it is set to the global scope.
        If this is not correct, unpickling will fail in some circumstances.

        `type`, if set, will be mixed in as the first base class.
        """
        if cls._member_map_:
            # simple value lookup if members exist
            if names is not _not_given:
                value = (value, names) + values
            return cls.__new__(cls, value)
        # otherwise, functional API: we're creating a new Enum type
        if names is _not_given and type is None:
            # no body? no data-type? possibly wrong usage
            raise TypeError(
                    f"{cls} has no members; specify `names=()` if you meant to create a new, empty, enum"
                    )
        return cls._create_(
                class_name=value,
                names=None if names is _not_given else names,
                module=module,
                qualname=qualname,
                type=type,
                start=start,
                boundary=boundary,
                )

    def __contains__(cls, value):
        """Return True if `value` is in `cls`.

        `value` is in `cls` if:
        1) `value` is a member of `cls`, or
        2) `value` is the value of one of the `cls`'s members.
        3) `value` is a pseudo-member (flags)
        """
        if isinstance(value, cls):
            return True
        if issubclass(cls, Flag):
            try:
                result = cls._missing_(value)
                return isinstance(result, cls)
            except ValueError:
                pass
        return (
                value in cls._unhashable_values_    # both structures are lists
                or value in cls._hashable_values_
                )

    def __delattr__(cls, attr):
        # nicer error message when someone tries to delete an attribute
        # (see issue19025).
        if attr in cls._member_map_:
            raise AttributeError("%r cannot delete member %r." % (cls.__name__, attr))
        super().__delattr__(attr)

    def __dir__(cls):
        interesting = set([
                '__class__', '__contains__', '__doc__', '__getitem__',
                '__iter__', '__len__', '__members__', '__module__',
                '__name__', '__qualname__',
                ]
                + cls._member_names_
                )
        if cls._new_member_ is not object.__new__:
            interesting.add('__new__')
        if cls.__init_subclass__ is not object.__init_subclass__:
            interesting.add('__init_subclass__')
        if cls._member_type_ is object:
            return sorted(interesting)
        else:
            # return whatever mixed-in data type has
            return sorted(set(dir(cls._member_type_)) | interesting)

    def __getitem__(cls, name):
        """
        Return the member matching `name`.
        """
        return cls._member_map_[name]

    def __iter__(cls):
        """
        Return members in definition order.
        """
        return (cls._member_map_[name] for name in cls._member_names_)

    def __len__(cls):
        """
        Return the number of members (no aliases)
        """
        return len(cls._member_names_)

    @bltns.property
    def __members__(cls):
        """
        Returns a mapping of member name->value.

        This mapping lists all enum members, including aliases.  Note that
        this is a read-only view of the internal mapping.
        """
        return MappingProxyType(cls._member_map_)

    def __repr__(cls):
        if Flag is not None and issubclass(cls, Flag):
            return "<flag %r>" % cls.__name__
        else:
            return "<enum %r>" % cls.__name__

    def __reversed__(cls):
        """
        Return members in reverse definition order.
        """
        return (cls._member_map_[name] for name in reversed(cls._member_names_))

    def __setattr__(cls, name, value):
        """
        Block attempts to reassign Enum members.

        A simple assignment to the class namespace only changes one of the
        several possible ways to get an Enum member from the Enum class,
        resulting in an inconsistent Enumeration.
        """
        member_map = cls.__dict__.get('_member_map_', {})
        if name in member_map:
            raise AttributeError('cannot reassign member %r' % (name, ))
        super().__setattr__(name, value)

    def _create_(cls, class_name, names, *, module=None, qualname=None, type=None, start=1, boundary=None):
        """
        Convenience method to create a new Enum class.

        `names` can be:

        * A string containing member names, separated either with spaces or
          commas.  Values are incremented by 1 from `start`.
        * An iterable of member names.  Values are incremented by 1 from `start`.
        * An iterable of (member name, value) pairs.
        * A mapping of member name -> value pairs.
        """
        metacls = cls.__class__
        bases = (cls, ) if type is None else (type, cls)
        _, first_enum = cls._get_mixins_(class_name, bases)
        classdict = metacls.__prepare__(class_name, bases)

        # special processing needed for names?
        if isinstance(names, str):
            names = names.replace(',', ' ').split()
        if isinstance(names, (tuple, list)) and names and isinstance(names[0], str):
            original_names, names = names, []
            last_values = []
            for count, name in enumerate(original_names):
                value = first_enum._generate_next_value_(name, start, count, last_values[:])
                last_values.append(value)
                names.append((name, value))
        if names is None:
            names = ()

        # Here, names is either an iterable of (name, value) or a mapping.
        for item in names:
            if isinstance(item, str):
                member_name, member_value = item, names[item]
            else:
                member_name, member_value = item
            classdict[member_name] = member_value

        if module is None:
            try:
                module = sys._getframemodulename(2)
            except AttributeError:
                # Fall back on _getframe if _getframemodulename is missing
                try:
                    module = sys._getframe(2).f_globals['__name__']
                except (AttributeError, ValueError, KeyError):
                    pass
        if module is None:
            _make_class_unpicklable(classdict)
        else:
            classdict['__module__'] = module
        if qualname is not None:
            classdict['__qualname__'] = qualname

        return metacls.__new__(metacls, class_name, bases, classdict, boundary=boundary)

    def _convert_(cls, name, module, filter, source=None, *, boundary=None, as_global=False):
        """
        Create a new Enum subclass that replaces a collection of global constants
        """
        # convert all constants from source (or module) that pass filter() to
        # a new Enum called name, and export the enum and its members back to
        # module;
        # also, replace the __reduce_ex__ method so unpickling works in
        # previous Python versions
        module_globals = sys.modules[module].__dict__
        if source:
            source = source.__dict__
        else:
            source = module_globals
        # _value2member_map_ is populated in the same order every time
        # for a consistent reverse mapping of number to name when there
        # are multiple names for the same number.
        members = [
                (name, value)
                for name, value in source.items()
                if filter(name)]
        try:
            # sort by value
            members.sort(key=lambda t: (t[1], t[0]))
        except TypeError:
            # unless some values aren't comparable, in which case sort by name
            members.sort(key=lambda t: t[0])
        body = {t[0]: t[1] for t in members}
        body['__module__'] = module
        tmp_cls = type(name, (object, ), body)
        cls = _simple_enum(etype=cls, boundary=boundary or KEEP)(tmp_cls)
        if as_global:
            global_enum(cls)
        else:
            sys.modules[cls.__module__].__dict__.update(cls.__members__)
        module_globals[name] = cls
        return cls

    @classmethod
    def _check_for_existing_members_(mcls, class_name, bases):
        for chain in bases:
            for base in chain.__mro__:
                if isinstance(base, EnumType) and base._member_names_:
                    raise TypeError(
                            "<enum %r> cannot extend %r"
                            % (class_name, base)
                            )

    @classmethod
    def _get_mixins_(mcls, class_name, bases):
        """
        Returns the type for creating enum members, and the first inherited
        enum class.

        bases: the tuple of bases that was given to __new__
        """
        if not bases:
            return object, Enum
        # ensure final parent class is an Enum derivative, find any concrete
        # data type, and check that Enum has no members
        first_enum = bases[-1]
        if not isinstance(first_enum, EnumType):
            raise TypeError("new enumerations should be created as "
                    "`EnumName([mixin_type, ...] [data_type,] enum_type)`")
        member_type = mcls._find_data_type_(class_name, bases) or object
        return member_type, first_enum

    @classmethod
    def _find_data_repr_(mcls, class_name, bases):
        for chain in bases:
            for base in chain.__mro__:
                if base is object:
                    continue
                elif isinstance(base, EnumType):
                    # if we hit an Enum, use it's _value_repr_
                    return base._value_repr_
                elif '__repr__' in base.__dict__:
                    # this is our data repr
                    # double-check if a dataclass with a default __repr__
                    if (
                            '__dataclass_fields__' in base.__dict__
                            and '__dataclass_params__' in base.__dict__
                            and base.__dict__['__dataclass_params__'].repr
                        ):
                        return _dataclass_repr
                    else:
                        return base.__dict__['__repr__']
        return None

    @classmethod
    def _find_data_type_(mcls, class_name, bases):
        # a datatype has a __new__ method, or a __dataclass_fields__ attribute
        data_types = set()
        base_chain = set()
        for chain in bases:
            candidate = None
            for base in chain.__mro__:
                base_chain.add(base)
                if base is object:
                    continue
                elif isinstance(base, EnumType):
                    if base._member_type_ is not object:
                        data_types.add(base._member_type_)
                        break
                elif '__new__' in base.__dict__ or '__dataclass_fields__' in base.__dict__:
                    data_types.add(candidate or base)
                    break
                else:
                    candidate = candidate or base
        if len(data_types) > 1:
            raise TypeError('too many data types for %r: %r' % (class_name, data_types))
        elif data_types:
            return data_types.pop()
        else:
            return None

    @classmethod
    def _find_new_(mcls, classdict, member_type, first_enum):
        """
        Returns the __new__ to be used for creating the enum members.

        classdict: the class dictionary given to __new__
        member_type: the data type whose __new__ will be used by default
        first_enum: enumeration to check for an overriding __new__
        """
        # now find the correct __new__, checking to see of one was defined
        # by the user; also check earlier enum classes in case a __new__ was
        # saved as __new_member__
        __new__ = classdict.get('__new__', None)

        # should __new__ be saved as __new_member__ later?
        save_new = first_enum is not None and __new__ is not None

        if __new__ is None:
            # check all possibles for __new_member__ before falling back to
            # __new__
            for method in ('__new_member__', '__new__'):
                for possible in (member_type, first_enum):
                    target = getattr(possible, method, None)
                    if target not in {
                            None,
                            None.__new__,
                            object.__new__,
                            Enum.__new__,
                            }:
                        __new__ = target
                        break
                if __new__ is not None:
                    break
            else:
                __new__ = object.__new__

        # if a non-object.__new__ is used then whatever value/tuple was
        # assigned to the enum member name will be passed to __new__ and to the
        # new enum member's __init__
        if first_enum is None or __new__ in (Enum.__new__, object.__new__):
            use_args = False
        else:
            use_args = True
        return __new__, save_new, use_args

    def _add_member_(cls, name, member):
        # _value_ structures are not updated
        if name in cls._member_map_:
            if cls._member_map_[name] is not member:
                raise NameError('%r is already bound: %r' % (name, cls._member_map_[name]))
            return
        #
        # if necessary, get redirect in place and then add it to _member_map_
        found_descriptor = None
        descriptor_type = None
        class_type = None
        for base in cls.__mro__[1:]:
            attr = base.__dict__.get(name)
            if attr is not None:
                if isinstance(attr, (property, DynamicClassAttribute)):
                    found_descriptor = attr
                    class_type = base
                    descriptor_type = 'enum'
                    break
                elif _is_descriptor(attr):
                    found_descriptor = attr
                    descriptor_type = descriptor_type or 'desc'
                    class_type = class_type or base
                    continue
                else:
                    descriptor_type = 'attr'
                    class_type = base
        if found_descriptor:
            redirect = property()
            redirect.member = member
            redirect.__set_name__(cls, name)
            if descriptor_type in ('enum', 'desc'):
                # earlier descriptor found; copy fget, fset, fdel to this one.
                redirect.fget = getattr(found_descriptor, 'fget', None)
                redirect._get = getattr(found_descriptor, '__get__', None)
                redirect.fset = getattr(found_descriptor, 'fset', None)
                redirect._set = getattr(found_descriptor, '__set__', None)
                redirect.fdel = getattr(found_descriptor, 'fdel', None)
                redirect._del = getattr(found_descriptor, '__delete__', None)
            redirect._attr_type = descriptor_type
            redirect._cls_type = class_type
            setattr(cls, name, redirect)
        else:
            setattr(cls, name, member)
        # now add to _member_map_ (even aliases)
        cls._member_map_[name] = member

    @property
    def __signature__(cls):
        from inspect import Parameter, Signature
        if cls._member_names_:
            return Signature([Parameter('values', Parameter.VAR_POSITIONAL)])
        else:
            return Signature([Parameter('new_class_name', Parameter.POSITIONAL_ONLY),
                              Parameter('names', Parameter.POSITIONAL_OR_KEYWORD),
                              Parameter('module', Parameter.KEYWORD_ONLY, default=None),
                              Parameter('qualname', Parameter.KEYWORD_ONLY, default=None),
                              Parameter('type', Parameter.KEYWORD_ONLY, default=None),
                              Parameter('start', Parameter.KEYWORD_ONLY, default=1),
                              Parameter('boundary', Parameter.KEYWORD_ONLY, default=None)])


EnumMeta = EnumType         # keep EnumMeta name for backwards compatibility


class Enum(metaclass=EnumType):
    """
    Create a collection of name/value pairs.

    Example enumeration:

    >>> class Color(Enum):
    ...     RED = 1
    ...     BLUE = 2
    ...     GREEN = 3

    Access them by:

    - attribute access:

      >>> Color.RED
      <Color.RED: 1>

    - value lookup:

      >>> Color(1)
      <Color.RED: 1>

    - name lookup:

      >>> Color['RED']
      <Color.RED: 1>

    Enumerations can be iterated over, and know how many members they have:

    >>> len(Color)
    3

    >>> list(Color)
    [<Color.RED: 1>, <Color.BLUE: 2>, <Color.GREEN: 3>]

    Methods can be added to enumerations, and members can have their own
    attributes -- see the documentation for details.
    """

    def __new__(cls, value):
        # all enum instances are actually created during class construction
        # without calling this method; this method is called by the metaclass'
        # __call__ (i.e. Color(3) ), and by pickle
        if type(value) is cls:
            # For lookups like Color(Color.RED)
            return value
        # by-value search for a matching enum member
        # see if it's in the reverse mapping (for hashable values)
        try:
            return cls._value2member_map_[value]
        except KeyError:
            # Not found, no need to do long O(n) search
            pass
        except TypeError:
            # not there, now do long search -- O(n) behavior
            for name, unhashable_values in cls._unhashable_values_map_.items():
                if value in unhashable_values:
                    return cls[name]
            for name, member in cls._member_map_.items():
                if value == member._value_:
                    return cls[name]
        # still not found -- verify that members exist, in-case somebody got here mistakenly
        # (such as via super when trying to override __new__)
        if not cls._member_map_:
            if getattr(cls, '_%s__in_progress' % cls.__name__, False):
                raise TypeError('do not use `super().__new__; call the appropriate __new__ directly') from None
            raise TypeError("%r has no members defined" % cls)
        #
        # still not found -- try _missing_ hook
        try:
            exc = None
            result = cls._missing_(value)
        except Exception as e:
            exc = e
            result = None
        try:
            if isinstance(result, cls):
                return result
            elif (
                    Flag is not None and issubclass(cls, Flag)
                    and cls._boundary_ is EJECT and isinstance(result, int)
                ):
                return result
            else:
                ve_exc = ValueError("%r is not a valid %s" % (value, cls.__qualname__))
                if result is None and exc is None:
                    raise ve_exc
                elif exc is None:
                    exc = TypeError(
                            'error in %s._missing_: returned %r instead of None or a valid member'
                            % (cls.__name__, result)
                            )
                if not isinstance(exc, ValueError):
                    exc.__context__ = ve_exc
                raise exc
        finally:
            # ensure all variables that could hold an exception are destroyed
            exc = None
            ve_exc = None

    def _add_alias_(self, name):
        self.__class__._add_member_(name, self)

    def _add_value_alias_(self, value):
        cls = self.__class__
        try:
            if value in cls._value2member_map_:
                if cls._value2member_map_[value] is not self:
                    raise ValueError('%r is already bound: %r' % (value, cls._value2member_map_[value]))
                return
        except TypeError:
            # unhashable value, do long search
            for m in cls._member_map_.values():
                if m._value_ == value:
                    if m is not self:
                        raise ValueError('%r is already bound: %r' % (value, cls._value2member_map_[value]))
                    return
        try:
            # This may fail if value is not hashable. We can't add the value
            # to the map, and by-value lookups for this value will be
            # linear.
            cls._value2member_map_.setdefault(value, self)
            cls._hashable_values_.append(value)
        except TypeError:
            # keep track of the value in a list so containment checks are quick
            cls._unhashable_values_.append(value)
            cls._unhashable_values_map_.setdefault(self.name, []).append(value)

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        """
        Generate the next value when not given.

        name: the name of the member
        start: the initial start value or None
        count: the number of existing members
        last_values: the list of values assigned
        """
        if not last_values:
            return start
        try:
            last_value = sorted(last_values).pop()
        except TypeError:
            raise TypeError('unable to sort non-numeric values') from None
        try:
            return last_value + 1
        except TypeError:
            raise TypeError('unable to increment %r' % (last_value, )) from None

    @classmethod
    def _missing_(cls, value):
        return None

    def __repr__(self):
        v_repr = self.__class__._value_repr_ or repr
        return "<%s.%s: %s>" % (self.__class__.__name__, self._name_, v_repr(self._value_))

    def __str__(self):
        return "%s.%s" % (self.__class__.__name__, self._name_, )

    def __dir__(self):
        """
        Returns public methods and other interesting attributes.
        """
        interesting = set()
        if self.__class__._member_type_ is not object:
            interesting = set(object.__dir__(self))
        for name in getattr(self, '__dict__', []):
            if name[0] != '_' and name not in self._member_map_:
                interesting.add(name)
        for cls in self.__class__.mro():
            for name, obj in cls.__dict__.items():
                if name[0] == '_':
                    continue
                if isinstance(obj, property):
                    # that's an enum.property
                    if obj.fget is not None or name not in self._member_map_:
                        interesting.add(name)
                    else:
                        # in case it was added by `dir(self)`
                        interesting.discard(name)
                elif name not in self._member_map_:
                    interesting.add(name)
        names = sorted(
                set(['__class__', '__doc__', '__eq__', '__hash__', '__module__'])
                | interesting
                )
        return names

    def __format__(self, format_spec):
        return str.__format__(str(self), format_spec)

    def __hash__(self):
        return hash(self._name_)

    def __reduce_ex__(self, proto):
        return self.__class__, (self._value_, )

    def __deepcopy__(self,memo):
        return self

    def __copy__(self):
        return self

    # enum.property is used to provide access to the `name` and
    # `value` attributes of enum members while keeping some measure of
    # protection from modification, while still allowing for an enumeration
    # to have members named `name` and `value`.  This works because each
    # instance of enum.property saves its companion member, which it returns
    # on class lookup; on instance lookup it either executes a provided function
    # or raises an AttributeError.

    @property
    def name(self):
        """The name of the Enum member."""
        return self._name_

    @property
    def value(self):
        """The value of the Enum member."""
        return self._value_


class ReprEnum(Enum):
    """
    Only changes the repr(), leaving str() and format() to the mixed-in type.
    """


class IntEnum(int, ReprEnum):
    """
    Enum where members are also (and must be) ints
    """


class StrEnum(str, ReprEnum):
    """
    Enum where members are also (and must be) strings
    """

    def __new__(cls, *values):
        "values must already be of type `str`"
        if len(values) > 3:
            raise TypeError('too many arguments for str(): %r' % (values, ))
        if len(values) == 1:
            # it must be a string
            if not isinstance(values[0], str):
                raise TypeError('%r is not a string' % (values[0], ))
        if len(values) >= 2:
            # check that encoding argument is a string
            if not isinstance(values[1], str):
                raise TypeError('encoding must be a string, not %r' % (values[1], ))
        if len(values) == 3:
            # check that errors argument is a string
            if not isinstance(values[2], str):
                raise TypeError('errors must be a string, not %r' % (values[2]))
        value = str(*values)
        member = str.__new__(cls, value)
        member._value_ = value
        return member

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        """
        Return the lower-cased version of the member name.
        """
        return name.lower()


def pickle_by_global_name(self, proto):
    # should not be used with Flag-type enums
    return self.name
_reduce_ex_by_global_name = pickle_by_global_name

def pickle_by_enum_name(self, proto):
    # should not be used with Flag-type enums
    return getattr, (self.__class__, self._name_)

class FlagBoundary(StrEnum):
    """
    control how out of range values are handled
    "strict" -> error is raised             [default for Flag]
    "conform" -> extra bits are discarded
    "eject" -> lose flag status
    "keep" -> keep flag status and all bits [default for IntFlag]
    """
    STRICT = auto()
    CONFORM = auto()
    EJECT = auto()
    KEEP = auto()
STRICT, CONFORM, EJECT, KEEP = FlagBoundary


class Flag(Enum, boundary=STRICT):
    """
    Support for flags
    """

    _numeric_repr_ = repr

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        """
        Generate the next value when not given.

        name: the name of the member
        start: the initial start value or None
        count: the number of existing members
        last_values: the last value assigned or None
        """
        if not count:
            return start if start is not None else 1
        last_value = max(last_values)
        try:
            high_bit = _high_bit(last_value)
        except Exception:
            raise TypeError('invalid flag value %r' % last_value) from None
        return 2 ** (high_bit+1)

    @classmethod
    def _iter_member_by_value_(cls, value):
        """
        Extract all members from the value in definition (i.e. increasing value) order.
        """
        for val in _iter_bits_lsb(value & cls._flag_mask_):
            yield cls._value2member_map_.get(val)

    _iter_member_ = _iter_member_by_value_

    @classmethod
    def _iter_member_by_def_(cls, value):
        """
        Extract all members from the value in definition order.
        """
        yield from sorted(
                cls._iter_member_by_value_(value),
                key=lambda m: m._sort_order_,
                )

    @classmethod
    def _missing_(cls, value):
        """
        Create a composite member containing all canonical members present in `value`.

        If non-member values are present, result depends on `_boundary_` setting.
        """
        if not isinstance(value, int):
            raise ValueError(
                    "%r is not a valid %s" % (value, cls.__qualname__)
                    )
        # check boundaries
        # - value must be in range (e.g. -16 <-> +15, i.e. ~15 <-> 15)
        # - value must not include any skipped flags (e.g. if bit 2 is not
        #   defined, then 0d10 is invalid)
        flag_mask = cls._flag_mask_
        singles_mask = cls._singles_mask_
        all_bits = cls._all_bits_
        neg_value = None
        if (
                not ~all_bits <= value <= all_bits
                or value & (all_bits ^ flag_mask)
            ):
            if cls._boundary_ is STRICT:
                max_bits = max(value.bit_length(), flag_mask.bit_length())
                raise ValueError(
                        "%r invalid value %r\n    given %s\n  allowed %s" % (
                            cls, value, bin(value, max_bits), bin(flag_mask, max_bits),
                            ))
            elif cls._boundary_ is CONFORM:
                value = value & flag_mask
            elif cls._boundary_ is EJECT:
                return value
            elif cls._boundary_ is KEEP:
                if value < 0:
                    value = (
                            max(all_bits+1, 2**(value.bit_length()))
                            + value
                            )
            else:
                raise ValueError(
                        '%r unknown flag boundary %r' % (cls, cls._boundary_, )
                        )
        if value < 0:
            neg_value = value
            value = all_bits + 1 + value
        # get members and unknown
        unknown = value & ~flag_mask
        aliases = value & ~singles_mask
        member_value = value & singles_mask
        if unknown and cls._boundary_ is not KEEP:
            raise ValueError(
                    '%s(%r) -->  unknown values %r [%s]'
                    % (cls.__name__, value, unknown, bin(unknown))
                    )
        # normal Flag?
        if cls._member_type_ is object:
            # construct a singleton enum pseudo-member
            pseudo_member = object.__new__(cls)
        else:
            pseudo_member = cls._member_type_.__new__(cls, value)
        if not hasattr(pseudo_member, '_value_'):
            pseudo_member._value_ = value
        if member_value or aliases:
            members = []
            combined_value = 0
            for m in cls._iter_member_(member_value):
                members.append(m)
                combined_value |= m._value_
            if aliases:
                value = member_value | aliases
                for n, pm in cls._member_map_.items():
                    if pm not in members and pm._value_ and pm._value_ & value == pm._value_:
                        members.append(pm)
                        combined_value |= pm._value_
            unknown = value ^ combined_value
            pseudo_member._name_ = '|'.join([m._name_ for m in members])
            if not combined_value:
                pseudo_member._name_ = None
            elif unknown and cls._boundary_ is STRICT:
                raise ValueError('%r: no members with value %r' % (cls, unknown))
            elif unknown:
                pseudo_member._name_ += '|%s' % cls._numeric_repr_(unknown)
        else:
            pseudo_member._name_ = None
        # use setdefault in case another thread already created a composite
        # with this value
        # note: zero is a special case -- always add it
        pseudo_member = cls._value2member_map_.setdefault(value, pseudo_member)
        if neg_value is not None:
            cls._value2member_map_[neg_value] = pseudo_member
        return pseudo_member

    def __contains__(self, other):
        """
        Returns True if self has at least the same flags set as other.
        """
        if not isinstance(other, self.__class__):
            raise TypeError(
                "unsupported operand type(s) for 'in': %r and %r" % (
                    type(other).__qualname__, self.__class__.__qualname__))
        return other._value_ & self._value_ == other._value_

    def __iter__(self):
        """
        Returns flags in definition order.
        """
        yield from self._iter_member_(self._value_)

    def __len__(self):
        return self._value_.bit_count()

    def __repr__(self):
        cls_name = self.__class__.__name__
        v_repr = self.__class__._value_repr_ or repr
        if self._name_ is None:
            return "<%s: %s>" % (cls_name, v_repr(self._value_))
        else:
            return "<%s.%s: %s>" % (cls_name, self._name_, v_repr(self._value_))

    def __str__(self):
        cls_name = self.__class__.__name__
        if self._name_ is None:
            return '%s(%r)' % (cls_name, self._value_)
        else:
            return "%s.%s" % (cls_name, self._name_)

    def __bool__(self):
        return bool(self._value_)

    def _get_value(self, flag):
        if isinstance(flag, self.__class__):
            return flag._value_
        elif self._member_type_ is not object and isinstance(flag, self._member_type_):
            return flag
        return NotImplemented

    def __or__(self, other):
        other_value = self._get_value(other)
        if other_value is NotImplemented:
            return NotImplemented

        for flag in self, other:
            if self._get_value(flag) is None:
                raise TypeError(f"'{flag}' cannot be combined with other flags with |")
        value = self._value_
        return self.__class__(value | other_value)

    def __and__(self, other):
        other_value = self._get_value(other)
        if other_value is NotImplemented:
            return NotImplemented

        for flag in self, other:
            if self._get_value(flag) is None:
                raise TypeError(f"'{flag}' cannot be combined with other flags with &")
        value = self._value_
        return self.__class__(value & other_value)

    def __xor__(self, other):
        other_value = self._get_value(other)
        if other_value is NotImplemented:
            return NotImplemented

        for flag in self, other:
            if self._get_value(flag) is None:
                raise TypeError(f"'{flag}' cannot be combined with other flags with ^")
        value = self._value_
        return self.__class__(value ^ other_value)

    def __invert__(self):
        if self._get_value(self) is None:
            raise TypeError(f"'{self}' cannot be inverted")

        if self._inverted_ is None:
            if self._boundary_ in (EJECT, KEEP):
                self._inverted_ = self.__class__(~self._value_)
            else:
                self._inverted_ = self.__class__(self._singles_mask_ & ~self._value_)
        return self._inverted_

    __rand__ = __and__
    __ror__ = __or__
    __rxor__ = __xor__


class IntFlag(int, ReprEnum, Flag, boundary=KEEP):
    """
    Support for integer-based Flags
    """


def _high_bit(value):
    """
    returns index of highest bit, or -1 if value is zero or negative
    """
    return value.bit_length() - 1

def unique(enumeration):
    """
    Class decorator for enumerations ensuring unique member values.
    """
    duplicates = []
    for name, member in enumeration.__members__.items():
        if name != member.name:
            duplicates.append((name, member.name))
    if duplicates:
        alias_details = ', '.join(
                ["%s -> %s" % (alias, name) for (alias, name) in duplicates])
        raise ValueError('duplicate values found in %r: %s' %
                (enumeration, alias_details))
    return enumeration

def _dataclass_repr(self):
    dcf = self.__dataclass_fields__
    return ', '.join(
            '%s=%r' % (k, getattr(self, k))
            for k in dcf.keys()
            if dcf[k].repr
            )

def global_enum_repr(self):
    """
    use module.enum_name instead of class.enum_name

    the module is the last module in case of a multi-module name
    """
    module = self.__class__.__module__.split('.')[-1]
    return '%s.%s' % (module, self._name_)

def global_flag_repr(self):
    """
    use module.flag_name instead of class.flag_name

    the module is the last module in case of a multi-module name
    """
    module = self.__class__.__module__.split('.')[-1]
    cls_name = self.__class__.__name__
    if self._name_ is None:
        return "%s.%s(%r)" % (module, cls_name, self._value_)
    if _is_single_bit(self._value_):
        return '%s.%s' % (module, self._name_)
    if self._boundary_ is not FlagBoundary.KEEP:
        return '|'.join(['%s.%s' % (module, name) for name in self.name.split('|')])
    else:
        name = []
        for n in self._name_.split('|'):
            if n[0].isdigit():
                name.append(n)
            else:
                name.append('%s.%s' % (module, n))
        return '|'.join(name)

def global_str(self):
    """
    use enum_name instead of class.enum_name
    """
    if self._name_ is None:
        cls_name = self.__class__.__name__
        return "%s(%r)" % (cls_name, self._value_)
    else:
        return self._name_

def global_enum(cls, update_str=False):
    """
    decorator that makes the repr() of an enum member reference its module
    instead of its class; also exports all members to the enum's module's
    global namespace
    """
    if issubclass(cls, Flag):
        cls.__repr__ = global_flag_repr
    else:
        cls.__repr__ = global_enum_repr
    if not issubclass(cls, ReprEnum) or update_str:
        cls.__str__ = global_str
    sys.modules[cls.__module__].__dict__.update(cls.__members__)
    return cls

def _simple_enum(etype=Enum, *, boundary=None, use_args=None):
    """
    Class decorator that converts a normal class into an :class:`Enum`.  No
    safety checks are done, and some advanced behavior (such as
    :func:`__init_subclass__`) is not available.  Enum creation can be faster
    using :func:`_simple_enum`.

        >>> from enum import Enum, _simple_enum
        >>> @_simple_enum(Enum)
        ... class Color:
        ...     RED = auto()
        ...     GREEN = auto()
        ...     BLUE = auto()
        >>> Color
        <enum 'Color'>
    """
    def convert_class(cls):
        nonlocal use_args
        cls_name = cls.__name__
        if use_args is None:
            use_args = etype._use_args_
        __new__ = cls.__dict__.get('__new__')
        if __new__ is not None:
            new_member = __new__.__func__
        else:
            new_member = etype._member_type_.__new__
        attrs = {}
        body = {}
        if __new__ is not None:
            body['__new_member__'] = new_member
        body['_new_member_'] = new_member
        body['_use_args_'] = use_args
        body['_generate_next_value_'] = gnv = etype._generate_next_value_
        body['_member_names_'] = member_names = []
        body['_member_map_'] = member_map = {}
        body['_value2member_map_'] = value2member_map = {}
        body['_hashable_values_'] = hashable_values = []
        body['_unhashable_values_'] = unhashable_values = []
        body['_unhashable_values_map_'] = {}
        body['_member_type_'] = member_type = etype._member_type_
        body['_value_repr_'] = etype._value_repr_
        if issubclass(etype, Flag):
            body['_boundary_'] = boundary or etype._boundary_
            body['_flag_mask_'] = None
            body['_all_bits_'] = None
            body['_singles_mask_'] = None
            body['_inverted_'] = None
            body['__or__'] = Flag.__or__
            body['__xor__'] = Flag.__xor__
            body['__and__'] = Flag.__and__
            body['__ror__'] = Flag.__ror__
            body['__rxor__'] = Flag.__rxor__
            body['__rand__'] = Flag.__rand__
            body['__invert__'] = Flag.__invert__
        for name, obj in cls.__dict__.items():
            if name in ('__dict__', '__weakref__'):
                continue
            if _is_dunder(name) or _is_private(cls_name, name) or _is_sunder(name) or _is_descriptor(obj):
                body[name] = obj
            else:
                attrs[name] = obj
        if cls.__dict__.get('__doc__') is None:
            body['__doc__'] = 'An enumeration.'
        #
        # double check that repr and friends are not the mixin's or various
        # things break (such as pickle)
        # however, if the method is defined in the Enum itself, don't replace
        # it
        enum_class = type(cls_name, (etype, ), body, boundary=boundary, _simple=True)
        for name in ('__repr__', '__str__', '__format__', '__reduce_ex__'):
            if name not in body:
                # check for mixin overrides before replacing
                enum_method = getattr(etype, name)
                found_method = getattr(enum_class, name)
                object_method = getattr(object, name)
                data_type_method = getattr(member_type, name)
                if found_method in (data_type_method, object_method):
                    setattr(enum_class, name, enum_method)
        gnv_last_values = []
        if issubclass(enum_class, Flag):
            # Flag / IntFlag
            single_bits = multi_bits = 0
            for name, value in attrs.items():
                if isinstance(value, auto) and auto.value is _auto_null:
                    value = gnv(name, 1, len(member_names), gnv_last_values)
                # create basic member (possibly isolate value for alias check)
                if use_args:
                    if not isinstance(value, tuple):
                        value = (value, )
                    member = new_member(enum_class, *value)
                    value = value[0]
                else:
                    member = new_member(enum_class)
                if __new__ is None:
                    member._value_ = value
                # now check if alias
                try:
                    contained = value2member_map.get(member._value_)
                except TypeError:
                    contained = None
                    if member._value_ in unhashable_values or member.value in hashable_values:
                        for m in enum_class:
                            if m._value_ == member._value_:
                                contained = m
                                break
                if contained is not None:
                    # an alias to an existing member
                    contained._add_alias_(name)
                else:
                    # finish creating member
                    member._name_ = name
                    member.__objclass__ = enum_class
                    member.__init__(value)
                    member._sort_order_ = len(member_names)
                    if name not in ('name', 'value'):
                        setattr(enum_class, name, member)
                        member_map[name] = member
                    else:
                        enum_class._add_member_(name, member)
                    value2member_map[value] = member
                    hashable_values.append(value)
                    if _is_single_bit(value):
                        # not a multi-bit alias, record in _member_names_ and _flag_mask_
                        member_names.append(name)
                        single_bits |= value
                    else:
                        multi_bits |= value
                    gnv_last_values.append(value)
            enum_class._flag_mask_ = single_bits | multi_bits
            enum_class._singles_mask_ = single_bits
            enum_class._all_bits_ = 2 ** ((single_bits|multi_bits).bit_length()) - 1
            # set correct __iter__
            member_list = [m._value_ for m in enum_class]
            if member_list != sorted(member_list):
                enum_class._iter_member_ = enum_class._iter_member_by_def_
        else:
            # Enum / IntEnum / StrEnum
            for name, value in attrs.items():
                if isinstance(value, auto):
                    if value.value is _auto_null:
                        value.value = gnv(name, 1, len(member_names), gnv_last_values)
                    value = value.value
                # create basic member (possibly isolate value for alias check)
                if use_args:
                    if not isinstance(value, tuple):
                        value = (value, )
                    member = new_member(enum_class, *value)
                    value = value[0]
                else:
                    member = new_member(enum_class)
                if __new__ is None:
                    member._value_ = value
                # now check if alias
                try:
                    contained = value2member_map.get(member._value_)
                except TypeError:
                    contained = None
                    if member._value_ in unhashable_values or member._value_ in hashable_values:
                        for m in enum_class:
                            if m._value_ == member._value_:
                                contained = m
                                break
                if contained is not None:
                    # an alias to an existing member
                    contained._add_alias_(name)
                else:
                    # finish creating member
                    member._name_ = name
                    member.__objclass__ = enum_class
                    member.__init__(value)
                    member._sort_order_ = len(member_names)
                    if name not in ('name', 'value'):
                        setattr(enum_class, name, member)
                        member_map[name] = member
                    else:
                        enum_class._add_member_(name, member)
                    member_names.append(name)
                    gnv_last_values.append(value)
                    try:
                        # This may fail if value is not hashable. We can't add the value
                        # to the map, and by-value lookups for this value will be
                        # linear.
                        enum_class._value2member_map_.setdefault(value, member)
                        if value not in hashable_values:
                            hashable_values.append(value)
                    except TypeError:
                        # keep track of the value in a list so containment checks are quick
                        enum_class._unhashable_values_.append(value)
                        enum_class._unhashable_values_map_.setdefault(name, []).append(value)
        if '__new__' in body:
            enum_class.__new_member__ = enum_class.__new__
        enum_class.__new__ = Enum.__new__
        return enum_class
    return convert_class

@_simple_enum(StrEnum)
class EnumCheck:
    """
    various conditions to check an enumeration for
    """
    CONTINUOUS = "no skipped integer values"
    NAMED_FLAGS = "multi-flag aliases may not contain unnamed flags"
    UNIQUE = "one name per value"
CONTINUOUS, NAMED_FLAGS, UNIQUE = EnumCheck


class verify:
    """
    Check an enumeration for various constraints. (see EnumCheck)
    """
    def __init__(self, *checks):
        self.checks = checks
    def __call__(self, enumeration):
        checks = self.checks
        cls_name = enumeration.__name__
        if Flag is not None and issubclass(enumeration, Flag):
            enum_type = 'flag'
        elif issubclass(enumeration, Enum):
            enum_type = 'enum'
        else:
            raise TypeError("the 'verify' decorator only works with Enum and Flag")
        for check in checks:
            if check is UNIQUE:
                # check for duplicate names
                duplicates = []
                for name, member in enumeration.__members__.items():
                    if name != member.name:
                        duplicates.append((name, member.name))
                if duplicates:
                    alias_details = ', '.join(
                            ["%s -> %s" % (alias, name) for (alias, name) in duplicates])
                    raise ValueError('aliases found in %r: %s' %
                            (enumeration, alias_details))
            elif check is CONTINUOUS:
                values = set(e.value for e in enumeration)
                if len(values) < 2:
                    continue
                low, high = min(values), max(values)
                missing = []
                if enum_type == 'flag':
                    # check for powers of two
                    for i in range(_high_bit(low)+1, _high_bit(high)):
                        if 2**i not in values:
                            missing.append(2**i)
                elif enum_type == 'enum':
                    # check for missing consecutive integers
                    for i in range(low+1, high):
                        if i not in values:
                            missing.append(i)
                else:
                    raise Exception('verify: unknown type %r' % enum_type)
                if missing:
                    raise ValueError(('invalid %s %r: missing values %s' % (
                            enum_type, cls_name, ', '.join((str(m) for m in missing)))
                            )[:256])
                            # limit max length to protect against DOS attacks
            elif check is NAMED_FLAGS:
                # examine each alias and check for unnamed flags
                member_names = enumeration._member_names_
                member_values = [m.value for m in enumeration]
                missing_names = []
                missing_value = 0
                for name, alias in enumeration._member_map_.items():
                    if name in member_names:
                        # not an alias
                        continue
                    if alias.value < 0:
                        # negative numbers are not checked
                        continue
                    values = list(_iter_bits_lsb(alias.value))
                    missed = [v for v in values if v not in member_values]
                    if missed:
                        missing_names.append(name)
                        for val in missed:
                            missing_value |= val
                if missing_names:
                    if len(missing_names) == 1:
                        alias = 'alias %s is missing' % missing_names[0]
                    else:
                        alias = 'aliases %s and %s are missing' % (
                                ', '.join(missing_names[:-1]), missing_names[-1]
                                )
                    if _is_single_bit(missing_value):
                        value = 'value 0x%x' % missing_value
                    else:
                        value = 'combined values of 0x%x' % missing_value
                    raise ValueError(
                            'invalid Flag %r: %s %s [use enum.show_flag_values(value) for details]'
                            % (cls_name, alias, value)
                            )
        return enumeration

def _test_simple_enum(checked_enum, simple_enum):
    """
    A function that can be used to test an enum created with :func:`_simple_enum`
    against the version created by subclassing :class:`Enum`::

        >>> from enum import Enum, _simple_enum, _test_simple_enum
        >>> @_simple_enum(Enum)
        ... class Color:
        ...     RED = auto()
        ...     GREEN = auto()
        ...     BLUE = auto()
        >>> class CheckedColor(Enum):
        ...     RED = auto()
        ...     GREEN = auto()
        ...     BLUE = auto()
        >>> _test_simple_enum(CheckedColor, Color)

    If differences are found, a :exc:`TypeError` is raised.
    """
    failed = []
    if checked_enum.__dict__ != simple_enum.__dict__:
        checked_dict = checked_enum.__dict__
        checked_keys = list(checked_dict.keys())
        simple_dict = simple_enum.__dict__
        simple_keys = list(simple_dict.keys())
        member_names = set(
                list(checked_enum._member_map_.keys())
                + list(simple_enum._member_map_.keys())
                )
        for key in set(checked_keys + simple_keys):
            if key in ('__module__', '_member_map_', '_value2member_map_', '__doc__',
                       '__static_attributes__', '__firstlineno__'):
                # keys known to be different, or very long
                continue
            elif key in member_names:
                # members are checked below
                continue
            elif key not in simple_keys:
                failed.append("missing key: %r" % (key, ))
            elif key not in checked_keys:
                failed.append("extra key:   %r" % (key, ))
            else:
                checked_value = checked_dict[key]
                simple_value = simple_dict[key]
                if callable(checked_value) or isinstance(checked_value, bltns.property):
                    continue
                if key == '__doc__':
                    # remove all spaces/tabs
                    compressed_checked_value = checked_value.replace(' ','').replace('\t','')
                    compressed_simple_value = simple_value.replace(' ','').replace('\t','')
                    if compressed_checked_value != compressed_simple_value:
                        failed.append("%r:\n         %s\n         %s" % (
                                key,
                                "checked -> %r" % (checked_value, ),
                                "simple  -> %r" % (simple_value, ),
                                ))
                elif checked_value != simple_value:
                    failed.append("%r:\n         %s\n         %s" % (
                            key,
                            "checked -> %r" % (checked_value, ),
                            "simple  -> %r" % (simple_value, ),
                            ))
        failed.sort()
        for name in member_names:
            failed_member = []
            if name not in simple_keys:
                failed.append('missing member from simple enum: %r' % name)
            elif name not in checked_keys:
                failed.append('extra member in simple enum: %r' % name)
            else:
                checked_member_dict = checked_enum[name].__dict__
                checked_member_keys = list(checked_member_dict.keys())
                simple_member_dict = simple_enum[name].__dict__
                simple_member_keys = list(simple_member_dict.keys())
                for key in set(checked_member_keys + simple_member_keys):
                    if key in ('__module__', '__objclass__', '_inverted_'):
                        # keys known to be different or absent
                        continue
                    elif key not in simple_member_keys:
                        failed_member.append("missing key %r not in the simple enum member %r" % (key, name))
                    elif key not in checked_member_keys:
                        failed_member.append("extra key %r in simple enum member %r" % (key, name))
                    else:
                        checked_value = checked_member_dict[key]
                        simple_value = simple_member_dict[key]
                        if checked_value != simple_value:
                            failed_member.append("%r:\n         %s\n         %s" % (
                                    key,
                                    "checked member -> %r" % (checked_value, ),
                                    "simple member  -> %r" % (simple_value, ),
                                    ))
            if failed_member:
                failed.append('%r member mismatch:\n      %s' % (
                        name, '\n      '.join(failed_member),
                        ))
        for method in (
                '__str__', '__repr__', '__reduce_ex__', '__format__',
                '__getnewargs_ex__', '__getnewargs__', '__reduce_ex__', '__reduce__'
            ):
            if method in simple_keys and method in checked_keys:
                # cannot compare functions, and it exists in both, so we're good
                continue
            elif method not in simple_keys and method not in checked_keys:
                # method is inherited -- check it out
                checked_method = getattr(checked_enum, method, None)
                simple_method = getattr(simple_enum, method, None)
                if hasattr(checked_method, '__func__'):
                    checked_method = checked_method.__func__
                    simple_method = simple_method.__func__
                if checked_method != simple_method:
                    failed.append("%r:  %-30s %s" % (
                            method,
                            "checked -> %r" % (checked_method, ),
                            "simple -> %r" % (simple_method, ),
                            ))
            else:
                # if the method existed in only one of the enums, it will have been caught
                # in the first checks above
                pass
    if failed:
        raise TypeError('enum mismatch:\n   %s' % '\n   '.join(failed))

def _old_convert_(etype, name, module, filter, source=None, *, boundary=None):
    """
    Create a new Enum subclass that replaces a collection of global constants
    """
    # convert all constants from source (or module) that pass filter() to
    # a new Enum called name, and export the enum and its members back to
    # module;
    # also, replace the __reduce_ex__ method so unpickling works in
    # previous Python versions
    module_globals = sys.modules[module].__dict__
    if source:
        source = source.__dict__
    else:
        source = module_globals
    # _value2member_map_ is populated in the same order every time
    # for a consistent reverse mapping of number to name when there
    # are multiple names for the same number.
    members = [
            (name, value)
            for name, value in source.items()
            if filter(name)]
    try:
        # sort by value
        members.sort(key=lambda t: (t[1], t[0]))
    except TypeError:
        # unless some values aren't comparable, in which case sort by name
        members.sort(key=lambda t: t[0])
    cls = etype(name, members, module=module, boundary=boundary or KEEP)
    return cls

_stdlib_enums = IntEnum, StrEnum, IntFlag
````

### ПУТЬ: Python/pythoncore-3.14-64/Lib/filecmp.py (320 строк, 10972 байт)

````python
"""Utilities for comparing files and directories.

Classes:
    dircmp

Functions:
    cmp(f1, f2, shallow=True) -> int
    cmpfiles(a, b, common) -> ([], [], [])
    clear_cache()

"""

import os
import stat
from itertools import filterfalse
from types import GenericAlias

__all__ = ['clear_cache', 'cmp', 'dircmp', 'cmpfiles', 'DEFAULT_IGNORES']

_cache = {}
BUFSIZE = 8*1024

DEFAULT_IGNORES = [
    'RCS', 'CVS', 'tags', '.git', '.hg', '.bzr', '_darcs', '__pycache__']

def clear_cache():
    """Clear the filecmp cache."""
    _cache.clear()

def cmp(f1, f2, shallow=True):
    """Compare two files.

    Arguments:

    f1 -- First file name

    f2 -- Second file name

    shallow -- treat files as identical if their stat signatures (type, size,
               mtime) are identical. Otherwise, files are considered different
               if their sizes or contents differ.  [default: True]

    Return value:

    True if the files are the same, False otherwise.

    This function uses a cache for past comparisons and the results,
    with cache entries invalidated if their stat information
    changes.  The cache may be cleared by calling clear_cache().

    """

    s1 = _sig(os.stat(f1))
    s2 = _sig(os.stat(f2))
    if s1[0] != stat.S_IFREG or s2[0] != stat.S_IFREG:
        return False
    if shallow and s1 == s2:
        return True
    if s1[1] != s2[1]:
        return False

    outcome = _cache.get((f1, f2, s1, s2))
    if outcome is None:
        outcome = _do_cmp(f1, f2)
        if len(_cache) > 100:      # limit the maximum size of the cache
            clear_cache()
        _cache[f1, f2, s1, s2] = outcome
    return outcome

def _sig(st):
    return (stat.S_IFMT(st.st_mode),
            st.st_size,
            st.st_mtime)

def _do_cmp(f1, f2):
    bufsize = BUFSIZE
    with open(f1, 'rb') as fp1, open(f2, 'rb') as fp2:
        while True:
            b1 = fp1.read(bufsize)
            b2 = fp2.read(bufsize)
            if b1 != b2:
                return False
            if not b1:
                return True

# Directory comparison class.
#
class dircmp:
    """A class that manages the comparison of 2 directories.

    dircmp(a, b, ignore=None, hide=None, *, shallow=True)
      A and B are directories.
      IGNORE is a list of names to ignore,
        defaults to DEFAULT_IGNORES.
      HIDE is a list of names to hide,
        defaults to [os.curdir, os.pardir].
      SHALLOW specifies whether to just check the stat signature (do not read
        the files).
        defaults to True.

    High level usage:
      x = dircmp(dir1, dir2)
      x.report() -> prints a report on the differences between dir1 and dir2
       or
      x.report_partial_closure() -> prints report on differences between dir1
            and dir2, and reports on common immediate subdirectories.
      x.report_full_closure() -> like report_partial_closure,
            but fully recursive.

    Attributes:
     left_list, right_list: The files in dir1 and dir2,
        filtered by hide and ignore.
     common: a list of names in both dir1 and dir2.
     left_only, right_only: names only in dir1, dir2.
     common_dirs: subdirectories in both dir1 and dir2.
     common_files: files in both dir1 and dir2.
     common_funny: names in both dir1 and dir2 where the type differs between
        dir1 and dir2, or the name is not stat-able.
     same_files: list of identical files.
     diff_files: list of filenames which differ.
     funny_files: list of files which could not be compared.
     subdirs: a dictionary of dircmp instances (or MyDirCmp instances if this
       object is of type MyDirCmp, a subclass of dircmp), keyed by names
       in common_dirs.
     """

    def __init__(self, a, b, ignore=None, hide=None, *, shallow=True): # Initialize
        self.left = a
        self.right = b
        if hide is None:
            self.hide = [os.curdir, os.pardir] # Names never to be shown
        else:
            self.hide = hide
        if ignore is None:
            self.ignore = DEFAULT_IGNORES
        else:
            self.ignore = ignore
        self.shallow = shallow

    def phase0(self): # Compare everything except common subdirectories
        self.left_list = _filter(os.listdir(self.left),
                                 self.hide+self.ignore)
        self.right_list = _filter(os.listdir(self.right),
                                  self.hide+self.ignore)
        self.left_list.sort()
        self.right_list.sort()

    def phase1(self): # Compute common names
        a = dict(zip(map(os.path.normcase, self.left_list), self.left_list))
        b = dict(zip(map(os.path.normcase, self.right_list), self.right_list))
        self.common = list(map(a.__getitem__, filter(b.__contains__, a)))
        self.left_only = list(map(a.__getitem__, filterfalse(b.__contains__, a)))
        self.right_only = list(map(b.__getitem__, filterfalse(a.__contains__, b)))

    def phase2(self): # Distinguish files, directories, funnies
        self.common_dirs = []
        self.common_files = []
        self.common_funny = []

        for x in self.common:
            a_path = os.path.join(self.left, x)
            b_path = os.path.join(self.right, x)

            ok = True
            try:
                a_stat = os.stat(a_path)
            except (OSError, ValueError):
                # See https://github.com/python/cpython/issues/122400
                # for the rationale for protecting against ValueError.
                # print('Can\'t stat', a_path, ':', why.args[1])
                ok = False
            try:
                b_stat = os.stat(b_path)
            except (OSError, ValueError):
                # print('Can\'t stat', b_path, ':', why.args[1])
                ok = False

            if ok:
                a_type = stat.S_IFMT(a_stat.st_mode)
                b_type = stat.S_IFMT(b_stat.st_mode)
                if a_type != b_type:
                    self.common_funny.append(x)
                elif stat.S_ISDIR(a_type):
                    self.common_dirs.append(x)
                elif stat.S_ISREG(a_type):
                    self.common_files.append(x)
                else:
                    self.common_funny.append(x)
            else:
                self.common_funny.append(x)

    def phase3(self): # Find out differences between common files
        xx = cmpfiles(self.left, self.right, self.common_files, self.shallow)
        self.same_files, self.diff_files, self.funny_files = xx

    def phase4(self): # Find out differences between common subdirectories
        # A new dircmp (or MyDirCmp if dircmp was subclassed) object is created
        # for each common subdirectory,
        # these are stored in a dictionary indexed by filename.
        # The hide and ignore properties are inherited from the parent
        self.subdirs = {}
        for x in self.common_dirs:
            a_x = os.path.join(self.left, x)
            b_x = os.path.join(self.right, x)
            self.subdirs[x]  = self.__class__(a_x, b_x, self.ignore, self.hide,
                                              shallow=self.shallow)

    def phase4_closure(self): # Recursively call phase4() on subdirectories
        self.phase4()
        for sd in self.subdirs.values():
            sd.phase4_closure()

    def report(self): # Print a report on the differences between a and b
        # Output format is purposely lousy
        print('diff', self.left, self.right)
        if self.left_only:
            self.left_only.sort()
            print('Only in', self.left, ':', self.left_only)
        if self.right_only:
            self.right_only.sort()
            print('Only in', self.right, ':', self.right_only)
        if self.same_files:
            self.same_files.sort()
            print('Identical files :', self.same_files)
        if self.diff_files:
            self.diff_files.sort()
            print('Differing files :', self.diff_files)
        if self.funny_files:
            self.funny_files.sort()
            print('Trouble with common files :', self.funny_files)
        if self.common_dirs:
            self.common_dirs.sort()
            print('Common subdirectories :', self.common_dirs)
        if self.common_funny:
            self.common_funny.sort()
            print('Common funny cases :', self.common_funny)

    def report_partial_closure(self): # Print reports on self and on subdirs
        self.report()
        for sd in self.subdirs.values():
            print()
            sd.report()

    def report_full_closure(self): # Report on self and subdirs recursively
        self.report()
        for sd in self.subdirs.values():
            print()
            sd.report_full_closure()

    methodmap = dict(subdirs=phase4,
                     same_files=phase3, diff_files=phase3, funny_files=phase3,
                     common_dirs=phase2, common_files=phase2, common_funny=phase2,
                     common=phase1, left_only=phase1, right_only=phase1,
                     left_list=phase0, right_list=phase0)

    def __getattr__(self, attr):
        if attr not in self.methodmap:
            raise AttributeError(attr)
        self.methodmap[attr](self)
        return getattr(self, attr)

    __class_getitem__ = classmethod(GenericAlias)


def cmpfiles(a, b, common, shallow=True):
    """Compare common files in two directories.

    a, b -- directory names
    common -- list of file names found in both directories
    shallow -- if true, do comparison based solely on stat() information

    Returns a tuple of three lists:
      files that compare equal
      files that are different
      filenames that aren't regular files.

    """
    res = ([], [], [])
    for x in common:
        ax = os.path.join(a, x)
        bx = os.path.join(b, x)
        res[_cmp(ax, bx, shallow)].append(x)
    return res


# Compare two files.
# Return:
#       0 for equal
#       1 for different
#       2 for funny cases (can't stat, NUL bytes, etc.)
#
def _cmp(a, b, sh, abs=abs, cmp=cmp):
    try:
        return not abs(cmp(a, b, sh))
    except (OSError, ValueError):
        return 2


# Return a copy with items that occur in skip removed.
#
def _filter(flist, skip):
    return list(filterfalse(skip.__contains__, flist))


# Demonstration and testing.
#
def demo():
    import sys
    import getopt
    options, args = getopt.getopt(sys.argv[1:], 'r')
    if len(args) != 2:
        raise getopt.GetoptError('need exactly two args', None)
    dd = dircmp(args[0], args[1])
    if ('-r', '') in options:
        dd.report_full_closure()
    else:
        dd.report()

if __name__ == '__main__':
    demo()
````

### ПУТЬ: Python/pythoncore-3.14-64/Lib/fileinput.py (442 строк, 16159 байт)

````python
"""Helper class to quickly write a loop over all standard input files.

Typical use is:

    import fileinput
    for line in fileinput.input(encoding="utf-8"):
        process(line)

This iterates over the lines of all files listed in sys.argv[1:],
defaulting to sys.stdin if the list is empty.  If a filename is '-' it
is also replaced by sys.stdin and the optional arguments mode and
openhook are ignored.  To specify an alternative list of filenames,
pass it as the argument to input().  A single file name is also allowed.

Functions filename(), lineno() return the filename and cumulative line
number of the line that has just been read; filelineno() returns its
line number in the current file; isfirstline() returns true iff the
line just read is the first line of its file; isstdin() returns true
iff the line was read from sys.stdin.  Function nextfile() closes the
current file so that the next iteration will read the first line from
the next file (if any); lines not read from the file will not count
towards the cumulative line count; the filename is not changed until
after the first line of the next file has been read.  Function close()
closes the sequence.

Before any lines have been read, filename() returns None and both line
numbers are zero; nextfile() has no effect.  After all lines have been
read, filename() and the line number functions return the values
pertaining to the last line read; nextfile() has no effect.

All files are opened in text mode by default, you can override this by
setting the mode parameter to input() or FileInput.__init__().
If an I/O error occurs during opening or reading a file, the OSError
exception is raised.

If sys.stdin is used more than once, the second and further use will
return no lines, except perhaps for interactive use, or if it has been
explicitly reset (e.g. using sys.stdin.seek(0)).

Empty files are opened and immediately closed; the only time their
presence in the list of filenames is noticeable at all is when the
last file opened is empty.

It is possible that the last line of a file doesn't end in a newline
character; otherwise lines are returned including the trailing
newline.

Class FileInput is the implementation; its methods filename(),
lineno(), fileline(), isfirstline(), isstdin(), nextfile() and close()
correspond to the functions in the module.  In addition it has a
readline() method which returns the next input line, and a
__getitem__() method which implements the sequence behavior.  The
sequence must be accessed in strictly sequential order; sequence
access and readline() cannot be mixed.

Optional in-place filtering: if the keyword argument inplace=True is
passed to input() or to the FileInput constructor, the file is moved
to a backup file and standard output is directed to the input file.
This makes it possible to write a filter that rewrites its input file
in place.  If the keyword argument backup=".<some extension>" is also
given, it specifies the extension for the backup file, and the backup
file remains around; by default, the extension is ".bak" and it is
deleted when the output file is closed.  In-place filtering is
disabled when standard input is read.  XXX The current implementation
does not work for MS-DOS 8+3 filesystems.
"""

import io
import sys, os
from types import GenericAlias

__all__ = ["input", "close", "nextfile", "filename", "lineno", "filelineno",
           "fileno", "isfirstline", "isstdin", "FileInput", "hook_compressed",
           "hook_encoded"]

_state = None

def input(files=None, inplace=False, backup="", *, mode="r", openhook=None,
          encoding=None, errors=None):
    """Return an instance of the FileInput class, which can be iterated.

    The parameters are passed to the constructor of the FileInput class.
    The returned instance, in addition to being an iterator,
    keeps global state for the functions of this module,.
    """
    global _state
    if _state and _state._file:
        raise RuntimeError("input() already active")
    _state = FileInput(files, inplace, backup, mode=mode, openhook=openhook,
                       encoding=encoding, errors=errors)
    return _state

def close():
    """Close the sequence."""
    global _state
    state = _state
    _state = None
    if state:
        state.close()

def nextfile():
    """
    Close the current file so that the next iteration will read the first
    line from the next file (if any); lines not read from the file will
    not count towards the cumulative line count. The filename is not
    changed until after the first line of the next file has been read.
    Before the first line has been read, this function has no effect;
    it cannot be used to skip the first file. After the last line of the
    last file has been read, this function has no effect.
    """
    if not _state:
        raise RuntimeError("no active input()")
    return _state.nextfile()

def filename():
    """
    Return the name of the file currently being read.
    Before the first line has been read, returns None.
    """
    if not _state:
        raise RuntimeError("no active input()")
    return _state.filename()

def lineno():
    """
    Return the cumulative line number of the line that has just been read.
    Before the first line has been read, returns 0. After the last line
    of the last file has been read, returns the line number of that line.
    """
    if not _state:
        raise RuntimeError("no active input()")
    return _state.lineno()

def filelineno():
    """
    Return the line number in the current file. Before the first line
    has been read, returns 0. After the last line of the last file has
    been read, returns the line number of that line within the file.
    """
    if not _state:
        raise RuntimeError("no active input()")
    return _state.filelineno()

def fileno():
    """
    Return the file number of the current file. When no file is currently
    opened, returns -1.
    """
    if not _state:
        raise RuntimeError("no active input()")
    return _state.fileno()

def isfirstline():
    """
    Returns true the line just read is the first line of its file,
    otherwise returns false.
    """
    if not _state:
        raise RuntimeError("no active input()")
    return _state.isfirstline()

def isstdin():
    """
    Returns true if the last line was read from sys.stdin,
    otherwise returns false.
    """
    if not _state:
        raise RuntimeError("no active input()")
    return _state.isstdin()

class FileInput:
    """FileInput([files[, inplace[, backup]]], *, mode=None, openhook=None)

    Class FileInput is the implementation of the module; its methods
    filename(), lineno(), fileline(), isfirstline(), isstdin(), fileno(),
    nextfile() and close() correspond to the functions of the same name
    in the module.
    In addition it has a readline() method which returns the next
    input line, and a __getitem__() method which implements the
    sequence behavior. The sequence must be accessed in strictly
    sequential order; random access and readline() cannot be mixed.
    """

    def __init__(self, files=None, inplace=False, backup="", *,
                 mode="r", openhook=None, encoding=None, errors=None):
        if isinstance(files, str):
            files = (files,)
        elif isinstance(files, os.PathLike):
            files = (os.fspath(files), )
        else:
            if files is None:
                files = sys.argv[1:]
            if not files:
                files = ('-',)
            else:
                files = tuple(files)
        self._files = files
        self._inplace = inplace
        self._backup = backup
        self._savestdout = None
        self._output = None
        self._filename = None
        self._startlineno = 0
        self._filelineno = 0
        self._file = None
        self._isstdin = False
        self._backupfilename = None
        self._encoding = encoding
        self._errors = errors

        # We can not use io.text_encoding() here because old openhook doesn't
        # take encoding parameter.
        if (sys.flags.warn_default_encoding and
                "b" not in mode and encoding is None and openhook is None):
            import warnings
            warnings.warn("'encoding' argument not specified.",
                          EncodingWarning, 2)

        # restrict mode argument to reading modes
        if mode not in ('r', 'rb'):
            raise ValueError("FileInput opening mode must be 'r' or 'rb'")
        self._mode = mode
        self._write_mode = mode.replace('r', 'w')
        if openhook:
            if inplace:
                raise ValueError("FileInput cannot use an opening hook in inplace mode")
            if not callable(openhook):
                raise ValueError("FileInput openhook must be callable")
        self._openhook = openhook

    def __del__(self):
        self.close()

    def close(self):
        try:
            self.nextfile()
        finally:
            self._files = ()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            line = self._readline()
            if line:
                self._filelineno += 1
                return line
            if not self._file:
                raise StopIteration
            self.nextfile()
            # repeat with next file

    def nextfile(self):
        savestdout = self._savestdout
        self._savestdout = None
        if savestdout:
            sys.stdout = savestdout

        output = self._output
        self._output = None
        try:
            if output:
                output.close()
        finally:
            file = self._file
            self._file = None
            try:
                del self._readline  # restore FileInput._readline
            except AttributeError:
                pass
            try:
                if file and not self._isstdin:
                    file.close()
            finally:
                backupfilename = self._backupfilename
                self._backupfilename = None
                if backupfilename and not self._backup:
                    try: os.unlink(backupfilename)
                    except OSError: pass

                self._isstdin = False

    def readline(self):
        while True:
            line = self._readline()
            if line:
                self._filelineno += 1
                return line
            if not self._file:
                return line
            self.nextfile()
            # repeat with next file

    def _readline(self):
        if not self._files:
            if 'b' in self._mode:
                return b''
            else:
                return ''
        self._filename = self._files[0]
        self._files = self._files[1:]
        self._startlineno = self.lineno()
        self._filelineno = 0
        self._file = None
        self._isstdin = False
        self._backupfilename = 0

        # EncodingWarning is emitted in __init__() already
        if "b" not in self._mode:
            encoding = self._encoding or "locale"
        else:
            encoding = None

        if self._filename == '-':
            self._filename = '<stdin>'
            if 'b' in self._mode:
                self._file = getattr(sys.stdin, 'buffer', sys.stdin)
            else:
                self._file = sys.stdin
            self._isstdin = True
        else:
            if self._inplace:
                self._backupfilename = (
                    os.fspath(self._filename) + (self._backup or ".bak"))
                try:
                    os.unlink(self._backupfilename)
                except OSError:
                    pass
                # The next few lines may raise OSError
                os.rename(self._filename, self._backupfilename)
                self._file = open(self._backupfilename, self._mode,
                                  encoding=encoding, errors=self._errors)
                try:
                    perm = os.fstat(self._file.fileno()).st_mode
                except OSError:
                    self._output = open(self._filename, self._write_mode,
                                        encoding=encoding, errors=self._errors)
                else:
                    mode = os.O_CREAT | os.O_WRONLY | os.O_TRUNC
                    if hasattr(os, 'O_BINARY'):
                        mode |= os.O_BINARY

                    fd = os.open(self._filename, mode, perm)
                    self._output = os.fdopen(fd, self._write_mode,
                                             encoding=encoding, errors=self._errors)
                    try:
                        os.chmod(self._filename, perm)
                    except OSError:
                        pass
                self._savestdout = sys.stdout
                sys.stdout = self._output
            else:
                # This may raise OSError
                if self._openhook:
                    # Custom hooks made previous to Python 3.10 didn't have
                    # encoding argument
                    if self._encoding is None:
                        self._file = self._openhook(self._filename, self._mode)
                    else:
                        self._file = self._openhook(
                            self._filename, self._mode, encoding=self._encoding, errors=self._errors)
                else:
                    self._file = open(self._filename, self._mode, encoding=encoding, errors=self._errors)
        self._readline = self._file.readline  # hide FileInput._readline
        return self._readline()

    def filename(self):
        return self._filename

    def lineno(self):
        return self._startlineno + self._filelineno

    def filelineno(self):
        return self._filelineno

    def fileno(self):
        if self._file:
            try:
                return self._file.fileno()
            except ValueError:
                return -1
        else:
            return -1

    def isfirstline(self):
        return self._filelineno == 1

    def isstdin(self):
        return self._isstdin

    __class_getitem__ = classmethod(GenericAlias)


def hook_compressed(filename, mode, *, encoding=None, errors=None):
    if encoding is None and "b" not in mode:  # EncodingWarning is emitted in FileInput() already.
        encoding = "locale"
    ext = os.path.splitext(filename)[1]
    if ext == '.gz':
        import gzip
        stream = gzip.open(filename, mode)
    elif ext == '.bz2':
        import bz2
        stream = bz2.BZ2File(filename, mode)
    else:
        return open(filename, mode, encoding=encoding, errors=errors)

    # gzip and bz2 are binary mode by default.
    if "b" not in mode:
        stream = io.TextIOWrapper(stream, encoding=encoding, errors=errors)
    return stream


def hook_encoded(encoding, errors=None):
    def openhook(filename, mode):
        return open(filename, mode, encoding=encoding, errors=errors)
    return openhook


def _test():
    import getopt
    inplace = False
    backup = False
    opts, args = getopt.getopt(sys.argv[1:], "ib:")
    for o, a in opts:
        if o == '-i': inplace = True
        if o == '-b': backup = a
    for line in input(args, inplace=inplace, backup=backup):
        if line[-1:] == '\n': line = line[:-1]
        if line[-1:] == '\r': line = line[:-1]
        print("%d: %s[%d]%s %s" % (lineno(), filename(), filelineno(),
                                   isfirstline() and "*" or "", line))
    print("%d: %s[%d]" % (lineno(), filename(), filelineno()))

if __name__ == '__main__':
    _test()
````

### ПУТЬ: Python/pythoncore-3.14-64/Lib/fnmatch.py (209 строк, 7000 байт)

````python
"""Filename matching with shell patterns.

fnmatch(FILENAME, PATTERN) matches according to the local convention.
fnmatchcase(FILENAME, PATTERN) always takes case in account.

The functions operate by translating the pattern into a regular
expression.  They cache the compiled regular expressions for speed.

The function translate(PATTERN) returns a regular expression
corresponding to PATTERN.  (It does not compile it.)
"""

import functools
import itertools
import os
import posixpath
import re

__all__ = ["filter", "filterfalse", "fnmatch", "fnmatchcase", "translate"]


def fnmatch(name, pat):
    """Test whether FILENAME matches PATTERN.

    Patterns are Unix shell style:

    *       matches everything
    ?       matches any single character
    [seq]   matches any character in seq
    [!seq]  matches any char not in seq

    An initial period in FILENAME is not special.
    Both FILENAME and PATTERN are first case-normalized
    if the operating system requires it.
    If you don't want this, use fnmatchcase(FILENAME, PATTERN).
    """
    name = os.path.normcase(name)
    pat = os.path.normcase(pat)
    return fnmatchcase(name, pat)


@functools.lru_cache(maxsize=32768, typed=True)
def _compile_pattern(pat):
    if isinstance(pat, bytes):
        pat_str = str(pat, 'ISO-8859-1')
        res_str = translate(pat_str)
        res = bytes(res_str, 'ISO-8859-1')
    else:
        res = translate(pat)
    return re.compile(res).match


def filter(names, pat):
    """Construct a list from those elements of the iterable NAMES that match PAT."""
    result = []
    pat = os.path.normcase(pat)
    match = _compile_pattern(pat)
    if os.path is posixpath:
        # normcase on posix is NOP. Optimize it away from the loop.
        for name in names:
            if match(name):
                result.append(name)
    else:
        for name in names:
            if match(os.path.normcase(name)):
                result.append(name)
    return result


def filterfalse(names, pat):
    """Construct a list from those elements of the iterable NAMES that do not match PAT."""
    pat = os.path.normcase(pat)
    match = _compile_pattern(pat)
    if os.path is posixpath:
        # normcase on posix is NOP. Optimize it away from the loop.
        return list(itertools.filterfalse(match, names))

    result = []
    for name in names:
        if match(os.path.normcase(name)) is None:
            result.append(name)
    return result


def fnmatchcase(name, pat):
    """Test whether FILENAME matches PATTERN, including case.

    This is a version of fnmatch() which doesn't case-normalize
    its arguments.
    """
    match = _compile_pattern(pat)
    return match(name) is not None


def translate(pat):
    """Translate a shell PATTERN to a regular expression.

    There is no way to quote meta-characters.
    """

    parts, star_indices = _translate(pat, '*', '.')
    return _join_translated_parts(parts, star_indices)


_re_setops_sub = re.compile(r'([&~|])').sub
_re_escape = functools.lru_cache(maxsize=512)(re.escape)


def _translate(pat, star, question_mark):
    res = []
    add = res.append
    star_indices = []

    i, n = 0, len(pat)
    while i < n:
        c = pat[i]
        i = i+1
        if c == '*':
            # store the position of the wildcard
            star_indices.append(len(res))
            add(star)
            # compress consecutive `*` into one
            while i < n and pat[i] == '*':
                i += 1
        elif c == '?':
            add(question_mark)
        elif c == '[':
            j = i
            if j < n and pat[j] == '!':
                j = j+1
            if j < n and pat[j] == ']':
                j = j+1
            while j < n and pat[j] != ']':
                j = j+1
            if j >= n:
                add('\\[')
            else:
                stuff = pat[i:j]
                if '-' not in stuff:
                    stuff = stuff.replace('\\', r'\\')
                else:
                    chunks = []
                    k = i+2 if pat[i] == '!' else i+1
                    while True:
                        k = pat.find('-', k, j)
                        if k < 0:
                            break
                        chunks.append(pat[i:k])
                        i = k+1
                        k = k+3
                    chunk = pat[i:j]
                    if chunk:
                        chunks.append(chunk)
                    else:
                        chunks[-1] += '-'
                    # Remove empty ranges -- invalid in RE.
                    for k in range(len(chunks)-1, 0, -1):
                        if chunks[k-1][-1] > chunks[k][0]:
                            chunks[k-1] = chunks[k-1][:-1] + chunks[k][1:]
                            del chunks[k]
                    # Escape backslashes and hyphens for set difference (--).
                    # Hyphens that create ranges shouldn't be escaped.
                    stuff = '-'.join(s.replace('\\', r'\\').replace('-', r'\-')
                                     for s in chunks)
                i = j+1
                if not stuff:
                    # Empty range: never match.
                    add('(?!)')
                elif stuff == '!':
                    # Negated empty range: match any character.
                    add('.')
                else:
                    # Escape set operations (&&, ~~ and ||).
                    stuff = _re_setops_sub(r'\\\1', stuff)
                    if stuff[0] == '!':
                        stuff = '^' + stuff[1:]
                    elif stuff[0] in ('^', '['):
                        stuff = '\\' + stuff
                    add(f'[{stuff}]')
        else:
            add(_re_escape(c))
    assert i == n
    return res, star_indices


def _join_translated_parts(parts, star_indices):
    if not star_indices:
        return fr'(?s:{"".join(parts)})\z'
    iter_star_indices = iter(star_indices)
    j = next(iter_star_indices)
    buffer = parts[:j]  # fixed pieces at the start
    append, extend = buffer.append, buffer.extend
    i = j + 1
    for j in iter_star_indices:
        # Now deal with STAR fixed STAR fixed ...
        # For an interior `STAR fixed` pairing, we want to do a minimal
        # .*? match followed by `fixed`, with no possibility of backtracking.
        # Atomic groups ("(?>...)") allow us to spell that directly.
        # Note: people rely on the undocumented ability to join multiple
        # translate() results together via "|" to build large regexps matching
        # "one of many" shell patterns.
        append('(?>.*?')
        extend(parts[i:j])
        append(')')
        i = j + 1
    append('.*')
    extend(parts[i:])
    res = ''.join(buffer)
    return fr'(?s:{res})\z'
````

### ПУТЬ: Python/pythoncore-3.14-64/Lib/fractions.py (1078 строк, 42531 байт)

````python
# Originally contributed by Sjoerd Mullender.
# Significantly modified by Jeffrey Yasskin <jyasskin at gmail.com>.

"""Fraction, infinite-precision, rational numbers."""

import functools
import math
import numbers
import operator
import re
import sys

__all__ = ['Fraction']


# Constants related to the hash implementation;  hash(x) is based
# on the reduction of x modulo the prime _PyHASH_MODULUS.
_PyHASH_MODULUS = sys.hash_info.modulus
# Value to be used for rationals that reduce to infinity modulo
# _PyHASH_MODULUS.
_PyHASH_INF = sys.hash_info.inf

@functools.lru_cache(maxsize = 1 << 14)
def _hash_algorithm(numerator, denominator):

    # To make sure that the hash of a Fraction agrees with the hash
    # of a numerically equal integer, float or Decimal instance, we
    # follow the rules for numeric hashes outlined in the
    # documentation.  (See library docs, 'Built-in Types').

    try:
        dinv = pow(denominator, -1, _PyHASH_MODULUS)
    except ValueError:
        # ValueError means there is no modular inverse.
        hash_ = _PyHASH_INF
    else:
        # The general algorithm now specifies that the absolute value of
        # the hash is
        #    (|N| * dinv) % P
        # where N is self._numerator and P is _PyHASH_MODULUS.  That's
        # optimized here in two ways:  first, for a non-negative int i,
        # hash(i) == i % P, but the int hash implementation doesn't need
        # to divide, and is faster than doing % P explicitly.  So we do
        #    hash(|N| * dinv)
        # instead.  Second, N is unbounded, so its product with dinv may
        # be arbitrarily expensive to compute.  The final answer is the
        # same if we use the bounded |N| % P instead, which can again
        # be done with an int hash() call.  If 0 <= i < P, hash(i) == i,
        # so this nested hash() call wastes a bit of time making a
        # redundant copy when |N| < P, but can save an arbitrarily large
        # amount of computation for large |N|.
        hash_ = hash(hash(abs(numerator)) * dinv)
    result = hash_ if numerator >= 0 else -hash_
    return -2 if result == -1 else result

_RATIONAL_FORMAT = re.compile(r"""
    \A\s*                                  # optional whitespace at the start,
    (?P<sign>[-+]?)                        # an optional sign, then
    (?=\d|\.\d)                            # lookahead for digit or .digit
    (?P<num>\d*|\d+(_\d+)*)                # numerator (possibly empty)
    (?:                                    # followed by
       (?:\s*/\s*(?P<denom>\d+(_\d+)*))?   # an optional denominator
    |                                      # or
       (?:\.(?P<decimal>\d*|\d+(_\d+)*))?  # an optional fractional part
       (?:E(?P<exp>[-+]?\d+(_\d+)*))?      # and optional exponent
    )
    \s*\z                                  # and optional whitespace to finish
""", re.VERBOSE | re.IGNORECASE)


# Helpers for formatting

def _round_to_exponent(n, d, exponent, no_neg_zero=False):
    """Round a rational number to the nearest multiple of a given power of 10.

    Rounds the rational number n/d to the nearest integer multiple of
    10**exponent, rounding to the nearest even integer multiple in the case of
    a tie. Returns a pair (sign: bool, significand: int) representing the
    rounded value (-1)**sign * significand * 10**exponent.

    If no_neg_zero is true, then the returned sign will always be False when
    the significand is zero. Otherwise, the sign reflects the sign of the
    input.

    d must be positive, but n and d need not be relatively prime.
    """
    if exponent >= 0:
        d *= 10**exponent
    else:
        n *= 10**-exponent

    # The divmod quotient is correct for round-ties-towards-positive-infinity;
    # In the case of a tie, we zero out the least significant bit of q.
    q, r = divmod(n + (d >> 1), d)
    if r == 0 and d & 1 == 0:
        q &= -2

    sign = q < 0 if no_neg_zero else n < 0
    return sign, abs(q)


def _round_to_figures(n, d, figures):
    """Round a rational number to a given number of significant figures.

    Rounds the rational number n/d to the given number of significant figures
    using the round-ties-to-even rule, and returns a triple
    (sign: bool, significand: int, exponent: int) representing the rounded
    value (-1)**sign * significand * 10**exponent.

    In the special case where n = 0, returns a significand of zero and
    an exponent of 1 - figures, for compatibility with formatting.
    Otherwise, the returned significand satisfies
    10**(figures - 1) <= significand < 10**figures.

    d must be positive, but n and d need not be relatively prime.
    figures must be positive.
    """
    # Special case for n == 0.
    if n == 0:
        return False, 0, 1 - figures

    # Find integer m satisfying 10**(m - 1) <= abs(n)/d <= 10**m. (If abs(n)/d
    # is a power of 10, either of the two possible values for m is fine.)
    str_n, str_d = str(abs(n)), str(d)
    m = len(str_n) - len(str_d) + (str_d <= str_n)

    # Round to a multiple of 10**(m - figures). The significand we get
    # satisfies 10**(figures - 1) <= significand <= 10**figures.
    exponent = m - figures
    sign, significand = _round_to_exponent(n, d, exponent)

    # Adjust in the case where significand == 10**figures, to ensure that
    # 10**(figures - 1) <= significand < 10**figures.
    if len(str(significand)) == figures + 1:
        significand //= 10
        exponent += 1

    return sign, significand, exponent


# Pattern for matching non-float-style format specifications.
_GENERAL_FORMAT_SPECIFICATION_MATCHER = re.compile(r"""
    (?:
        (?P<fill>.)?
        (?P<align>[<>=^])
    )?
    (?P<sign>[-+ ]?)
    # Alt flag forces a slash and denominator in the output, even for
    # integer-valued Fraction objects.
    (?P<alt>\#)?
    # We don't implement the zeropad flag since there's no single obvious way
    # to interpret it.
    (?P<minimumwidth>0|[1-9][0-9]*)?
    (?P<thousands_sep>[,_])?
""", re.DOTALL | re.VERBOSE).fullmatch


# Pattern for matching float-style format specifications;
# supports 'e', 'E', 'f', 'F', 'g', 'G' and '%' presentation types.
_FLOAT_FORMAT_SPECIFICATION_MATCHER = re.compile(r"""
    (?:
        (?P<fill>.)?
        (?P<align>[<>=^])
    )?
    (?P<sign>[-+ ]?)
    (?P<no_neg_zero>z)?
    (?P<alt>\#)?
    # A '0' that's *not* followed by another digit is parsed as a minimum width
    # rather than a zeropad flag.
    (?P<zeropad>0(?=[0-9]))?
    (?P<minimumwidth>[0-9]+)?
    (?P<thousands_sep>[,_])?
    (?:\.
        (?=[,_0-9])  # lookahead for digit or separator
        (?P<precision>[0-9]+)?
        (?P<frac_separators>[,_])?
    )?
    (?P<presentation_type>[eEfFgG%])
""", re.DOTALL | re.VERBOSE).fullmatch


class Fraction(numbers.Rational):
    """This class implements rational numbers.

    In the two-argument form of the constructor, Fraction(8, 6) will
    produce a rational number equivalent to 4/3. Both arguments must
    be Rational. The numerator defaults to 0 and the denominator
    defaults to 1 so that Fraction(3) == 3 and Fraction() == 0.

    Fractions can also be constructed from:

      - numeric strings similar to those accepted by the
        float constructor (for example, '-2.3' or '1e10')

      - strings of the form '123/456'

      - float and Decimal instances

      - other Rational instances (including integers)

    """

    __slots__ = ('_numerator', '_denominator')

    # We're immutable, so use __new__ not __init__
    def __new__(cls, numerator=0, denominator=None):
        """Constructs a Rational.

        Takes a string like '3/2' or '1.5', another Rational instance, a
        numerator/denominator pair, or a float.

        Examples
        --------

        >>> Fraction(10, -8)
        Fraction(-5, 4)
        >>> Fraction(Fraction(1, 7), 5)
        Fraction(1, 35)
        >>> Fraction(Fraction(1, 7), Fraction(2, 3))
        Fraction(3, 14)
        >>> Fraction('314')
        Fraction(314, 1)
        >>> Fraction('-35/4')
        Fraction(-35, 4)
        >>> Fraction('3.1415') # conversion from numeric string
        Fraction(6283, 2000)
        >>> Fraction('-47e-2') # string may include a decimal exponent
        Fraction(-47, 100)
        >>> Fraction(1.47)  # direct construction from float (exact conversion)
        Fraction(6620291452234629, 4503599627370496)
        >>> Fraction(2.25)
        Fraction(9, 4)
        >>> Fraction(Decimal('1.47'))
        Fraction(147, 100)

        """
        self = super(Fraction, cls).__new__(cls)

        if denominator is None:
            if type(numerator) is int:
                self._numerator = numerator
                self._denominator = 1
                return self

            elif isinstance(numerator, numbers.Rational):
                self._numerator = numerator.numerator
                self._denominator = numerator.denominator
                return self

            elif (isinstance(numerator, float) or
                  (not isinstance(numerator, type) and
                   hasattr(numerator, 'as_integer_ratio'))):
                # Exact conversion
                self._numerator, self._denominator = numerator.as_integer_ratio()
                return self

            elif isinstance(numerator, str):
                # Handle construction from strings.
                m = _RATIONAL_FORMAT.match(numerator)
                if m is None:
                    raise ValueError('Invalid literal for Fraction: %r' %
                                     numerator)
                numerator = int(m.group('num') or '0')
                denom = m.group('denom')
                if denom:
                    denominator = int(denom)
                else:
                    denominator = 1
                    decimal = m.group('decimal')
                    if decimal:
                        decimal = decimal.replace('_', '')
                        scale = 10**len(decimal)
                        numerator = numerator * scale + int(decimal)
                        denominator *= scale
                    exp = m.group('exp')
                    if exp:
                        exp = int(exp)
                        if exp >= 0:
                            numerator *= 10**exp
                        else:
                            denominator *= 10**-exp
                if m.group('sign') == '-':
                    numerator = -numerator

            else:
                raise TypeError("argument should be a string or a Rational "
                                "instance or have the as_integer_ratio() method")

        elif type(numerator) is int is type(denominator):
            pass # *very* normal case

        elif (isinstance(numerator, numbers.Rational) and
            isinstance(denominator, numbers.Rational)):
            numerator, denominator = (
                numerator.numerator * denominator.denominator,
                denominator.numerator * numerator.denominator
                )
        else:
            raise TypeError("both arguments should be "
                            "Rational instances")

        if denominator == 0:
            raise ZeroDivisionError('Fraction(%s, 0)' % numerator)
        g = math.gcd(numerator, denominator)
        if denominator < 0:
            g = -g
        numerator //= g
        denominator //= g
        self._numerator = numerator
        self._denominator = denominator
        return self

    @classmethod
    def from_number(cls, number):
        """Converts a finite real number to a rational number, exactly.

        Beware that Fraction.from_number(0.3) != Fraction(3, 10).

        """
        if type(number) is int:
            return cls._from_coprime_ints(number, 1)

        elif isinstance(number, numbers.Rational):
            return cls._from_coprime_ints(number.numerator, number.denominator)

        elif (isinstance(number, float) or
              (not isinstance(number, type) and
               hasattr(number, 'as_integer_ratio'))):
            return cls._from_coprime_ints(*number.as_integer_ratio())

        else:
            raise TypeError("argument should be a Rational instance or "
                            "have the as_integer_ratio() method")

    @classmethod
    def from_float(cls, f):
        """Converts a finite float to a rational number, exactly.

        Beware that Fraction.from_float(0.3) != Fraction(3, 10).

        """
        if isinstance(f, numbers.Integral):
            return cls(f)
        elif not isinstance(f, float):
            raise TypeError("%s.from_float() only takes floats, not %r (%s)" %
                            (cls.__name__, f, type(f).__name__))
        return cls._from_coprime_ints(*f.as_integer_ratio())

    @classmethod
    def from_decimal(cls, dec):
        """Converts a finite Decimal instance to a rational number, exactly."""
        from decimal import Decimal
        if isinstance(dec, numbers.Integral):
            dec = Decimal(int(dec))
        elif not isinstance(dec, Decimal):
            raise TypeError(
                "%s.from_decimal() only takes Decimals, not %r (%s)" %
                (cls.__name__, dec, type(dec).__name__))
        return cls._from_coprime_ints(*dec.as_integer_ratio())

    @classmethod
    def _from_coprime_ints(cls, numerator, denominator, /):
        """Convert a pair of ints to a rational number, for internal use.

        The ratio of integers should be in lowest terms and the denominator
        should be positive.
        """
        obj = super(Fraction, cls).__new__(cls)
        obj._numerator = numerator
        obj._denominator = denominator
        return obj

    def is_integer(self):
        """Return True if the Fraction is an integer."""
        return self._denominator == 1

    def as_integer_ratio(self):
        """Return a pair of integers, whose ratio is equal to the original Fraction.

        The ratio is in lowest terms and has a positive denominator.
        """
        return (self._numerator, self._denominator)

    def limit_denominator(self, max_denominator=1000000):
        """Closest Fraction to self with denominator at most max_denominator.

        >>> Fraction('3.141592653589793').limit_denominator(10)
        Fraction(22, 7)
        >>> Fraction('3.141592653589793').limit_denominator(100)
        Fraction(311, 99)
        >>> Fraction(4321, 8765).limit_denominator(10000)
        Fraction(4321, 8765)

        """
        # Algorithm notes: For any real number x, define a *best upper
        # approximation* to x to be a rational number p/q such that:
        #
        #   (1) p/q >= x, and
        #   (2) if p/q > r/s >= x then s > q, for any rational r/s.
        #
        # Define *best lower approximation* similarly.  Then it can be
        # proved that a rational number is a best upper or lower
        # approximation to x if, and only if, it is a convergent or
        # semiconvergent of the (unique shortest) continued fraction
        # associated to x.
        #
        # To find a best rational approximation with denominator <= M,
        # we find the best upper and lower approximations with
        # denominator <= M and take whichever of these is closer to x.
        # In the event of a tie, the bound with smaller denominator is
        # chosen.  If both denominators are equal (which can happen
        # only when max_denominator == 1 and self is midway between
        # two integers) the lower bound---i.e., the floor of self, is
        # taken.

        if max_denominator < 1:
            raise ValueError("max_denominator should be at least 1")
        if self._denominator <= max_denominator:
            return Fraction(self)

        p0, q0, p1, q1 = 0, 1, 1, 0
        n, d = self._numerator, self._denominator
        while True:
            a = n//d
            q2 = q0+a*q1
            if q2 > max_denominator:
                break
            p0, q0, p1, q1 = p1, q1, p0+a*p1, q2
            n, d = d, n-a*d
        k = (max_denominator-q0)//q1

        # Determine which of the candidates (p0+k*p1)/(q0+k*q1) and p1/q1 is
        # closer to self. The distance between them is 1/(q1*(q0+k*q1)), while
        # the distance from p1/q1 to self is d/(q1*self._denominator). So we
        # need to compare 2*(q0+k*q1) with self._denominator/d.
        if 2*d*(q0+k*q1) <= self._denominator:
            return Fraction._from_coprime_ints(p1, q1)
        else:
            return Fraction._from_coprime_ints(p0+k*p1, q0+k*q1)

    @property
    def numerator(a):
        return a._numerator

    @property
    def denominator(a):
        return a._denominator

    def __repr__(self):
        """repr(self)"""
        return '%s(%s, %s)' % (self.__class__.__name__,
                               self._numerator, self._denominator)

    def __str__(self):
        """str(self)"""
        if self._denominator == 1:
            return str(self._numerator)
        else:
            return '%s/%s' % (self._numerator, self._denominator)

    def _format_general(self, match):
        """Helper method for __format__.

        Handles fill, alignment, signs, and thousands separators in the
        case of no presentation type.
        """
        # Validate and parse the format specifier.
        fill = match["fill"] or " "
        align = match["align"] or ">"
        pos_sign = "" if match["sign"] == "-" else match["sign"]
        alternate_form = bool(match["alt"])
        minimumwidth = int(match["minimumwidth"] or "0")
        thousands_sep = match["thousands_sep"] or ''

        # Determine the body and sign representation.
        n, d = self._numerator, self._denominator
        if d > 1 or alternate_form:
            body = f"{abs(n):{thousands_sep}}/{d:{thousands_sep}}"
        else:
            body = f"{abs(n):{thousands_sep}}"
        sign = '-' if n < 0 else pos_sign

        # Pad with fill character if necessary and return.
        padding = fill * (minimumwidth - len(sign) - len(body))
        if align == ">":
            return padding + sign + body
        elif align == "<":
            return sign + body + padding
        elif align == "^":
            half = len(padding) // 2
            return padding[:half] + sign + body + padding[half:]
        else:  # align == "="
            return sign + padding + body

    def _format_float_style(self, match):
        """Helper method for __format__; handles float presentation types."""
        fill = match["fill"] or " "
        align = match["align"] or ">"
        pos_sign = "" if match["sign"] == "-" else match["sign"]
        no_neg_zero = bool(match["no_neg_zero"])
        alternate_form = bool(match["alt"])
        zeropad = bool(match["zeropad"])
        minimumwidth = int(match["minimumwidth"] or "0")
        thousands_sep = match["thousands_sep"]
        precision = int(match["precision"] or "6")
        frac_sep = match["frac_separators"] or ""
        presentation_type = match["presentation_type"]
        trim_zeros = presentation_type in "gG" and not alternate_form
        trim_point = not alternate_form
        exponent_indicator = "E" if presentation_type in "EFG" else "e"

        if align == '=' and fill == '0':
            zeropad = True

        # Round to get the digits we need, figure out where to place the point,
        # and decide whether to use scientific notation. 'point_pos' is the
        # relative to the _end_ of the digit string: that is, it's the number
        # of digits that should follow the point.
        if presentation_type in "fF%":
            exponent = -precision
            if presentation_type == "%":
                exponent -= 2
            negative, significand = _round_to_exponent(
                self._numerator, self._denominator, exponent, no_neg_zero)
            scientific = False
            point_pos = precision
        else:  # presentation_type in "eEgG"
            figures = (
                max(precision, 1)
                if presentation_type in "gG"
                else precision + 1
            )
            negative, significand, exponent = _round_to_figures(
                self._numerator, self._denominator, figures)
            scientific = (
                presentation_type in "eE"
                or exponent > 0
                or exponent + figures <= -4
            )
            point_pos = figures - 1 if scientific else -exponent

        # Get the suffix - the part following the digits, if any.
        if presentation_type == "%":
            suffix = "%"
        elif scientific:
            suffix = f"{exponent_indicator}{exponent + point_pos:+03d}"
        else:
            suffix = ""

        # String of output digits, padded sufficiently with zeros on the left
        # so that we'll have at least one digit before the decimal point.
        digits = f"{significand:0{point_pos + 1}d}"

        # Before padding, the output has the form f"{sign}{leading}{trailing}",
        # where `leading` includes thousands separators if necessary and
        # `trailing` includes the decimal separator where appropriate.
        sign = "-" if negative else pos_sign
        leading = digits[: len(digits) - point_pos]
        frac_part = digits[len(digits) - point_pos :]
        if trim_zeros:
            frac_part = frac_part.rstrip("0")
        separator = "" if trim_point and not frac_part else "."
        if frac_sep:
            frac_part = frac_sep.join(frac_part[pos:pos + 3]
                                      for pos in range(0, len(frac_part), 3))
        trailing = separator + frac_part + suffix

        # Do zero padding if required.
        if zeropad:
            min_leading = minimumwidth - len(sign) - len(trailing)
            # When adding thousands separators, they'll be added to the
            # zero-padded portion too, so we need to compensate.
            leading = leading.zfill(
                3 * min_leading // 4 + 1 if thousands_sep else min_leading
            )

        # Insert thousands separators if required.
        if thousands_sep:
            first_pos = 1 + (len(leading) - 1) % 3
            leading = leading[:first_pos] + "".join(
                thousands_sep + leading[pos : pos + 3]
                for pos in range(first_pos, len(leading), 3)
            )

        # We now have a sign and a body. Pad with fill character if necessary
        # and return.
        body = leading + trailing
        padding = fill * (minimumwidth - len(sign) - len(body))
        if align == ">":
            return padding + sign + body
        elif align == "<":
            return sign + body + padding
        elif align == "^":
            half = len(padding) // 2
            return padding[:half] + sign + body + padding[half:]
        else:  # align == "="
            return sign + padding + body

    def __format__(self, format_spec, /):
        """Format this fraction according to the given format specification."""

        if match := _GENERAL_FORMAT_SPECIFICATION_MATCHER(format_spec):
            return self._format_general(match)

        if match := _FLOAT_FORMAT_SPECIFICATION_MATCHER(format_spec):
            # Refuse the temptation to guess if both alignment _and_
            # zero padding are specified.
            if match["align"] is None or match["zeropad"] is None:
                return self._format_float_style(match)

        raise ValueError(
            f"Invalid format specifier {format_spec!r} "
            f"for object of type {type(self).__name__!r}"
        )

    def _operator_fallbacks(monomorphic_operator, fallback_operator,
                            handle_complex=True):
        """Generates forward and reverse operators given a purely-rational
        operator and a function from the operator module.

        Use this like:
        __op__, __rop__ = _operator_fallbacks(just_rational_op, operator.op)

        In general, we want to implement the arithmetic operations so
        that mixed-mode operations either call an implementation whose
        author knew about the types of both arguments, or convert both
        to the nearest built in type and do the operation there. In
        Fraction, that means that we define __add__ and __radd__ as:

            def __add__(self, other):
                # Both types have numerators/denominator attributes,
                # so do the operation directly
                if isinstance(other, (int, Fraction)):
                    return Fraction(self.numerator * other.denominator +
                                    other.numerator * self.denominator,
                                    self.denominator * other.denominator)
                # float and complex don't have those operations, but we
                # know about those types, so special case them.
                elif isinstance(other, float):
                    return float(self) + other
                elif isinstance(other, complex):
                    return complex(self) + other
                # Let the other type take over.
                return NotImplemented

            def __radd__(self, other):
                # radd handles more types than add because there's
                # nothing left to fall back to.
                if isinstance(other, numbers.Rational):
                    return Fraction(self.numerator * other.denominator +
                                    other.numerator * self.denominator,
                                    self.denominator * other.denominator)
                elif isinstance(other, Real):
                    return float(other) + float(self)
                elif isinstance(other, Complex):
                    return complex(other) + complex(self)
                return NotImplemented


        There are 5 different cases for a mixed-type addition on
        Fraction. I'll refer to all of the above code that doesn't
        refer to Fraction, float, or complex as "boilerplate". 'r'
        will be an instance of Fraction, which is a subtype of
        Rational (r : Fraction <: Rational), and b : B <:
        Complex. The first three involve 'r + b':

            1. If B <: Fraction, int, float, or complex, we handle
               that specially, and all is well.
            2. If Fraction falls back to the boilerplate code, and it
               were to return a value from __add__, we'd miss the
               possibility that B defines a more intelligent __radd__,
               so the boilerplate should return NotImplemented from
               __add__. In particular, we don't handle Rational
               here, even though we could get an exact answer, in case
               the other type wants to do something special.
            3. If B <: Fraction, Python tries B.__radd__ before
               Fraction.__add__. This is ok, because it was
               implemented with knowledge of Fraction, so it can
               handle those instances before delegating to Real or
               Complex.

        The next two situations describe 'b + r'. We assume that b
        didn't know about Fraction in its implementation, and that it
        uses similar boilerplate code:

            4. If B <: Rational, then __radd_ converts both to the
               builtin rational type (hey look, that's us) and
               proceeds.
            5. Otherwise, __radd__ tries to find the nearest common
               base ABC, and fall back to its builtin type. Since this
               class doesn't subclass a concrete type, there's no
               implementation to fall back to, so we need to try as
               hard as possible to return an actual value, or the user
               will get a TypeError.

        """
        def forward(a, b):
            if isinstance(b, Fraction):
                return monomorphic_operator(a, b)
            elif isinstance(b, int):
                return monomorphic_operator(a, Fraction(b))
            elif isinstance(b, float):
                return fallback_operator(float(a), b)
            elif handle_complex and isinstance(b, complex):
                return fallback_operator(float(a), b)
            else:
                return NotImplemented
        forward.__name__ = '__' + fallback_operator.__name__ + '__'
        forward.__doc__ = monomorphic_operator.__doc__

        def reverse(b, a):
            if isinstance(a, numbers.Rational):
                # Includes ints.
                return monomorphic_operator(Fraction(a), b)
            elif isinstance(a, numbers.Real):
                return fallback_operator(float(a), float(b))
            elif handle_complex and isinstance(a, numbers.Complex):
                return fallback_operator(complex(a), float(b))
            else:
                return NotImplemented
        reverse.__name__ = '__r' + fallback_operator.__name__ + '__'
        reverse.__doc__ = monomorphic_operator.__doc__

        return forward, reverse

    # Rational arithmetic algorithms: Knuth, TAOCP, Volume 2, 4.5.1.
    #
    # Assume input fractions a and b are normalized.
    #
    # 1) Consider addition/subtraction.
    #
    # Let g = gcd(da, db). Then
    #
    #              na   nb    na*db ± nb*da
    #     a ± b == -- ± -- == ------------- ==
    #              da   db        da*db
    #
    #              na*(db//g) ± nb*(da//g)    t
    #           == ----------------------- == -
    #                      (da*db)//g         d
    #
    # Now, if g > 1, we're working with smaller integers.
    #
    # Note, that t, (da//g) and (db//g) are pairwise coprime.
    #
    # Indeed, (da//g) and (db//g) share no common factors (they were
    # removed) and da is coprime with na (since input fractions are
    # normalized), hence (da//g) and na are coprime.  By symmetry,
    # (db//g) and nb are coprime too.  Then,
    #
    #     gcd(t, da//g) == gcd(na*(db//g), da//g) == 1
    #     gcd(t, db//g) == gcd(nb*(da//g), db//g) == 1
    #
    # Above allows us optimize reduction of the result to lowest
    # terms.  Indeed,
    #
    #     g2 = gcd(t, d) == gcd(t, (da//g)*(db//g)*g) == gcd(t, g)
    #
    #                       t//g2                   t//g2
    #     a ± b == ----------------------- == ----------------
    #              (da//g)*(db//g)*(g//g2)    (da//g)*(db//g2)
    #
    # is a normalized fraction.  This is useful because the unnormalized
    # denominator d could be much larger than g.
    #
    # We should special-case g == 1 (and g2 == 1), since 60.8% of
    # randomly-chosen integers are coprime:
    # https://en.wikipedia.org/wiki/Coprime_integers#Probability_of_coprimality
    # Note, that g2 == 1 always for fractions, obtained from floats: here
    # g is a power of 2 and the unnormalized numerator t is an odd integer.
    #
    # 2) Consider multiplication
    #
    # Let g1 = gcd(na, db) and g2 = gcd(nb, da), then
    #
    #            na*nb    na*nb    (na//g1)*(nb//g2)
    #     a*b == ----- == ----- == -----------------
    #            da*db    db*da    (db//g1)*(da//g2)
    #
    # Note, that after divisions we're multiplying smaller integers.
    #
    # Also, the resulting fraction is normalized, because each of
    # two factors in the numerator is coprime to each of the two factors
    # in the denominator.
    #
    # Indeed, pick (na//g1).  It's coprime with (da//g2), because input
    # fractions are normalized.  It's also coprime with (db//g1), because
    # common factors are removed by g1 == gcd(na, db).
    #
    # As for addition/subtraction, we should special-case g1 == 1
    # and g2 == 1 for same reason.  That happens also for multiplying
    # rationals, obtained from floats.

    def _add(a, b):
        """a + b"""
        na, da = a._numerator, a._denominator
        nb, db = b._numerator, b._denominator
        g = math.gcd(da, db)
        if g == 1:
            return Fraction._from_coprime_ints(na * db + da * nb, da * db)
        s = da // g
        t = na * (db // g) + nb * s
        g2 = math.gcd(t, g)
        if g2 == 1:
            return Fraction._from_coprime_ints(t, s * db)
        return Fraction._from_coprime_ints(t // g2, s * (db // g2))

    __add__, __radd__ = _operator_fallbacks(_add, operator.add)

    def _sub(a, b):
        """a - b"""
        na, da = a._numerator, a._denominator
        nb, db = b._numerator, b._denominator
        g = math.gcd(da, db)
        if g == 1:
            return Fraction._from_coprime_ints(na * db - da * nb, da * db)
        s = da // g
        t = na * (db // g) - nb * s
        g2 = math.gcd(t, g)
        if g2 == 1:
            return Fraction._from_coprime_ints(t, s * db)
        return Fraction._from_coprime_ints(t // g2, s * (db // g2))

    __sub__, __rsub__ = _operator_fallbacks(_sub, operator.sub)

    def _mul(a, b):
        """a * b"""
        na, da = a._numerator, a._denominator
        nb, db = b._numerator, b._denominator
        g1 = math.gcd(na, db)
        if g1 > 1:
            na //= g1
            db //= g1
        g2 = math.gcd(nb, da)
        if g2 > 1:
            nb //= g2
            da //= g2
        return Fraction._from_coprime_ints(na * nb, db * da)

    __mul__, __rmul__ = _operator_fallbacks(_mul, operator.mul)

    def _div(a, b):
        """a / b"""
        # Same as _mul(), with inversed b.
        nb, db = b._numerator, b._denominator
        if nb == 0:
            raise ZeroDivisionError('Fraction(%s, 0)' % db)
        na, da = a._numerator, a._denominator
        g1 = math.gcd(na, nb)
        if g1 > 1:
            na //= g1
            nb //= g1
        g2 = math.gcd(db, da)
        if g2 > 1:
            da //= g2
            db //= g2
        n, d = na * db, nb * da
        if d < 0:
            n, d = -n, -d
        return Fraction._from_coprime_ints(n, d)

    __truediv__, __rtruediv__ = _operator_fallbacks(_div, operator.truediv)

    def _floordiv(a, b):
        """a // b"""
        return (a.numerator * b.denominator) // (a.denominator * b.numerator)

    __floordiv__, __rfloordiv__ = _operator_fallbacks(_floordiv, operator.floordiv, False)

    def _divmod(a, b):
        """(a // b, a % b)"""
        da, db = a.denominator, b.denominator
        div, n_mod = divmod(a.numerator * db, da * b.numerator)
        return div, Fraction(n_mod, da * db)

    __divmod__, __rdivmod__ = _operator_fallbacks(_divmod, divmod, False)

    def _mod(a, b):
        """a % b"""
        da, db = a.denominator, b.denominator
        return Fraction((a.numerator * db) % (b.numerator * da), da * db)

    __mod__, __rmod__ = _operator_fallbacks(_mod, operator.mod, False)

    def __pow__(a, b, modulo=None):
        """a ** b

        If b is not an integer, the result will be a float or complex
        since roots are generally irrational. If b is an integer, the
        result will be rational.

        """
        if modulo is not None:
            return NotImplemented
        if isinstance(b, numbers.Rational):
            if b.denominator == 1:
                power = b.numerator
                if power >= 0:
                    return Fraction._from_coprime_ints(a._numerator ** power,
                                                       a._denominator ** power)
                elif a._numerator > 0:
                    return Fraction._from_coprime_ints(a._denominator ** -power,
                                                       a._numerator ** -power)
                elif a._numerator == 0:
                    raise ZeroDivisionError('Fraction(%s, 0)' %
                                            a._denominator ** -power)
                else:
                    return Fraction._from_coprime_ints((-a._denominator) ** -power,
                                                       (-a._numerator) ** -power)
            else:
                # A fractional power will generally produce an
                # irrational number.
                return float(a) ** float(b)
        elif isinstance(b, (float, complex)):
            return float(a) ** b
        else:
            return NotImplemented

    def __rpow__(b, a, modulo=None):
        """a ** b"""
        if modulo is not None:
            return NotImplemented
        if b._denominator == 1 and b._numerator >= 0:
            # If a is an int, keep it that way if possible.
            return a ** b._numerator

        if isinstance(a, numbers.Rational):
            return Fraction(a.numerator, a.denominator) ** b

        if b._denominator == 1:
            return a ** b._numerator

        return a ** float(b)

    def __pos__(a):
        """+a: Coerces a subclass instance to Fraction"""
        return Fraction._from_coprime_ints(a._numerator, a._denominator)

    def __neg__(a):
        """-a"""
        return Fraction._from_coprime_ints(-a._numerator, a._denominator)

    def __abs__(a):
        """abs(a)"""
        return Fraction._from_coprime_ints(abs(a._numerator), a._denominator)

    def __int__(a, _index=operator.index):
        """int(a)"""
        if a._numerator < 0:
            return _index(-(-a._numerator // a._denominator))
        else:
            return _index(a._numerator // a._denominator)

    def __trunc__(a):
        """math.trunc(a)"""
        if a._numerator < 0:
            return -(-a._numerator // a._denominator)
        else:
            return a._numerator // a._denominator

    def __floor__(a):
        """math.floor(a)"""
        return a._numerator // a._denominator

    def __ceil__(a):
        """math.ceil(a)"""
        # The negations cleverly convince floordiv to return the ceiling.
        return -(-a._numerator // a._denominator)

    def __round__(self, ndigits=None):
        """round(self, ndigits)

        Rounds half toward even.
        """
        if ndigits is None:
            d = self._denominator
            floor, remainder = divmod(self._numerator, d)
            if remainder * 2 < d:
                return floor
            elif remainder * 2 > d:
                return floor + 1
            # Deal with the half case:
            elif floor % 2 == 0:
                return floor
            else:
                return floor + 1
        shift = 10**abs(ndigits)
        # See _operator_fallbacks.forward to check that the results of
        # these operations will always be Fraction and therefore have
        # round().
        if ndigits > 0:
            return Fraction(round(self * shift), shift)
        else:
            return Fraction(round(self / shift) * shift)

    def __hash__(self):
        """hash(self)"""
        return _hash_algorithm(self._numerator, self._denominator)

    def __eq__(a, b):
        """a == b"""
        if type(b) is int:
            return a._numerator == b and a._denominator == 1
        if isinstance(b, numbers.Rational):
            return (a._numerator == b.numerator and
                    a._denominator == b.denominator)
        if isinstance(b, numbers.Complex) and b.imag == 0:
            b = b.real
        if isinstance(b, float):
            if math.isnan(b) or math.isinf(b):
                # comparisons with an infinity or nan should behave in
                # the same way for any finite a, so treat a as zero.
                return 0.0 == b
            else:
                return a == a.from_float(b)
        else:
            # Since a doesn't know how to compare with b, let's give b
            # a chance to compare itself with a.
            return NotImplemented

    def _richcmp(self, other, op):
        """Helper for comparison operators, for internal use only.

        Implement comparison between a Rational instance `self`, and
        either another Rational instance or a float `other`.  If
        `other` is not a Rational instance or a float, return
        NotImplemented. `op` should be one of the six standard
        comparison operators.

        """
        # convert other to a Rational instance where reasonable.
        if isinstance(other, numbers.Rational):
            return op(self._numerator * other.denominator,
                      self._denominator * other.numerator)
        if isinstance(other, float):
            if math.isnan(other) or math.isinf(other):
                return op(0.0, other)
            else:
                return op(self, self.from_float(other))
        else:
            return NotImplemented

    def __lt__(a, b):
        """a < b"""
        return a._richcmp(b, operator.lt)

    def __gt__(a, b):
        """a > b"""
        return a._richcmp(b, operator.gt)

    def __le__(a, b):
        """a <= b"""
        return a._richcmp(b, operator.le)

    def __ge__(a, b):
        """a >= b"""
        return a._richcmp(b, operator.ge)

    def __bool__(a):
        """a != 0"""
        # bpo-39274: Use bool() because (a._numerator != 0) can return an
        # object which is not a bool.
        return bool(a._numerator)

    # support for pickling, copy, and deepcopy

    def __reduce__(self):
        return (self.__class__, (self._numerator, self._denominator))

    def __copy__(self):
        if type(self) == Fraction:
            return self     # I'm immutable; therefore I am my own clone
        return self.__class__(self._numerator, self._denominator)

    def __deepcopy__(self, memo):
        if type(self) == Fraction:
            return self     # My components are also immutable
        return self.__class__(self._numerator, self._denominator)
````

### ПУТЬ: Python/pythoncore-3.14-64/Lib/ftplib.py (975 строк, 36215 байт)

````python
"""An FTP client class and some helper functions.

Based on RFC 959: File Transfer Protocol (FTP), by J. Postel and J. Reynolds

Example:

>>> from ftplib import FTP
>>> ftp = FTP('ftp.python.org') # connect to host, default port
>>> ftp.login() # default, i.e.: user anonymous, passwd anonymous@
'230 Guest login ok, access restrictions apply.'
>>> ftp.retrlines('LIST') # list directory contents
total 9
drwxr-xr-x   8 root     wheel        1024 Jan  3  1994 .
drwxr-xr-x   8 root     wheel        1024 Jan  3  1994 ..
drwxr-xr-x   2 root     wheel        1024 Jan  3  1994 bin
drwxr-xr-x   2 root     wheel        1024 Jan  3  1994 etc
d-wxrwxr-x   2 ftp      wheel        1024 Sep  5 13:43 incoming
drwxr-xr-x   2 root     wheel        1024 Nov 17  1993 lib
drwxr-xr-x   6 1094     wheel        1024 Sep 13 19:07 pub
drwxr-xr-x   3 root     wheel        1024 Jan  3  1994 usr
-rw-r--r--   1 root     root          312 Aug  1  1994 welcome.msg
'226 Transfer complete.'
>>> ftp.quit()
'221 Goodbye.'
>>>

A nice test that reveals some of the network dialogue would be:
python ftplib.py -d localhost -l -p -l
"""

#
# Changes and improvements suggested by Steve Majewski.
# Modified by Jack to work on the mac.
# Modified by Siebren to support docstrings and PASV.
# Modified by Phil Schwartz to add storbinary and storlines callbacks.
# Modified by Giampaolo Rodola' to add TLS support.
#

import sys
import socket
from socket import _GLOBAL_DEFAULT_TIMEOUT

__all__ = ["FTP", "error_reply", "error_temp", "error_perm", "error_proto",
           "all_errors"]

# Magic number from <socket.h>
MSG_OOB = 0x1                           # Process data out of band


# The standard FTP server control port
FTP_PORT = 21
# The sizehint parameter passed to readline() calls
MAXLINE = 8192


# Exception raised when an error or invalid response is received
class Error(Exception): pass
class error_reply(Error): pass          # unexpected [123]xx reply
class error_temp(Error): pass           # 4xx errors
class error_perm(Error): pass           # 5xx errors
class error_proto(Error): pass          # response does not begin with [1-5]


# All exceptions (hopefully) that may be raised here and that aren't
# (always) programming errors on our side
all_errors = (Error, OSError, EOFError)


# Line terminators (we always output CRLF, but accept any of CRLF, CR, LF)
CRLF = '\r\n'
B_CRLF = b'\r\n'

# The class itself
class FTP:
    '''An FTP client class.

    To create a connection, call the class using these arguments:
            host, user, passwd, acct, timeout, source_address, encoding

    The first four arguments are all strings, and have default value ''.
    The parameter ´timeout´ must be numeric and defaults to None if not
    passed, meaning that no timeout will be set on any ftp socket(s).
    If a timeout is passed, then this is now the default timeout for all ftp
    socket operations for this instance.
    The last parameter is the encoding of filenames, which defaults to utf-8.

    Then use self.connect() with optional host and port argument.

    To download a file, use ftp.retrlines('RETR ' + filename),
    or ftp.retrbinary() with slightly different arguments.
    To upload a file, use ftp.storlines() or ftp.storbinary(),
    which have an open file as argument (see their definitions
    below for details).
    The download/upload functions first issue appropriate TYPE
    and PORT or PASV commands.
    '''

    debugging = 0
    host = ''
    port = FTP_PORT
    maxline = MAXLINE
    sock = None
    file = None
    welcome = None
    passiveserver = True
    # Disables https://bugs.python.org/issue43285 security if set to True.
    trust_server_pasv_ipv4_address = False

    def __init__(self, host='', user='', passwd='', acct='',
                 timeout=_GLOBAL_DEFAULT_TIMEOUT, source_address=None, *,
                 encoding='utf-8'):
        """Initialization method (called by class instantiation).
        Initialize host to localhost, port to standard ftp port.
        Optional arguments are host (for connect()),
        and user, passwd, acct (for login()).
        """
        self.encoding = encoding
        self.source_address = source_address
        self.timeout = timeout
        if host:
            self.connect(host)
            if user:
                self.login(user, passwd, acct)

    def __enter__(self):
        return self

    # Context management protocol: try to quit() if active
    def __exit__(self, *args):
        if self.sock is not None:
            try:
                self.quit()
            except (OSError, EOFError):
                pass
            finally:
                if self.sock is not None:
                    self.close()

    def connect(self, host='', port=0, timeout=-999, source_address=None):
        '''Connect to host.  Arguments are:
         - host: hostname to connect to (string, default previous host)
         - port: port to connect to (integer, default previous port)
         - timeout: the timeout to set against the ftp socket(s)
         - source_address: a 2-tuple (host, port) for the socket to bind
           to as its source address before connecting.
        '''
        if host != '':
            self.host = host
        if port > 0:
            self.port = port
        if timeout != -999:
            self.timeout = timeout
        if self.timeout is not None and not self.timeout:
            raise ValueError('Non-blocking socket (timeout=0) is not supported')
        if source_address is not None:
            self.source_address = source_address
        sys.audit("ftplib.connect", self, self.host, self.port)
        self.sock = socket.create_connection((self.host, self.port), self.timeout,
                                             source_address=self.source_address)
        self.af = self.sock.family
        self.file = self.sock.makefile('r', encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome

    def getwelcome(self):
        '''Get the welcome message from the server.
        (this is read and squirreled away by connect())'''
        if self.debugging:
            print('*welcome*', self.sanitize(self.welcome))
        return self.welcome

    def set_debuglevel(self, level):
        '''Set the debugging level.
        The required argument level means:
        0: no debugging output (default)
        1: print commands and responses but not body text etc.
        2: also print raw lines read and sent before stripping CR/LF'''
        self.debugging = level
    debug = set_debuglevel

    def set_pasv(self, val):
        '''Use passive or active mode for data transfers.
        With a false argument, use the normal PORT mode,
        With a true argument, use the PASV command.'''
        self.passiveserver = val

    # Internal: "sanitize" a string for printing
    def sanitize(self, s):
        if s[:5] in {'pass ', 'PASS '}:
            i = len(s.rstrip('\r\n'))
            s = s[:5] + '*'*(i-5) + s[i:]
        return repr(s)

    # Internal: send one line to the server, appending CRLF
    def putline(self, line):
        if '\r' in line or '\n' in line:
            raise ValueError('an illegal newline character should not be contained')
        sys.audit("ftplib.sendcmd", self, line)
        line = line + CRLF
        if self.debugging > 1:
            print('*put*', self.sanitize(line))
        self.sock.sendall(line.encode(self.encoding))

    # Internal: send one command to the server (through putline())
    def putcmd(self, line):
        if self.debugging: print('*cmd*', self.sanitize(line))
        self.putline(line)

    # Internal: return one line from the server, stripping CRLF.
    # Raise EOFError if the connection is closed
    def getline(self):
        line = self.file.readline(self.maxline + 1)
        if len(line) > self.maxline:
            raise Error("got more than %d bytes" % self.maxline)
        if self.debugging > 1:
            print('*get*', self.sanitize(line))
        if not line:
            raise EOFError
        if line[-2:] == CRLF:
            line = line[:-2]
        elif line[-1:] in CRLF:
            line = line[:-1]
        return line

    # Internal: get a response from the server, which may possibly
    # consist of multiple lines.  Return a single string with no
    # trailing CRLF.  If the response consists of multiple lines,
    # these are separated by '\n' characters in the string
    def getmultiline(self):
        line = self.getline()
        if line[3:4] == '-':
            code = line[:3]
            while 1:
                nextline = self.getline()
                line = line + ('\n' + nextline)
                if nextline[:3] == code and \
                        nextline[3:4] != '-':
                    break
        return line

    # Internal: get a response from the server.
    # Raise various errors if the response indicates an error
    def getresp(self):
        resp = self.getmultiline()
        if self.debugging:
            print('*resp*', self.sanitize(resp))
        self.lastresp = resp[:3]
        c = resp[:1]
        if c in {'1', '2', '3'}:
            return resp
        if c == '4':
            raise error_temp(resp)
        if c == '5':
            raise error_perm(resp)
        raise error_proto(resp)

    def voidresp(self):
        """Expect a response beginning with '2'."""
        resp = self.getresp()
        if resp[:1] != '2':
            raise error_reply(resp)
        return resp

    def abort(self):
        '''Abort a file transfer.  Uses out-of-band data.
        This does not follow the procedure from the RFC to send Telnet
        IP and Synch; that doesn't seem to work with the servers I've
        tried.  Instead, just send the ABOR command as OOB data.'''
        line = b'ABOR' + B_CRLF
        if self.debugging > 1:
            print('*put urgent*', self.sanitize(line))
        self.sock.sendall(line, MSG_OOB)
        resp = self.getmultiline()
        if resp[:3] not in {'426', '225', '226'}:
            raise error_proto(resp)
        return resp

    def sendcmd(self, cmd):
        '''Send a command and return the response.'''
        self.putcmd(cmd)
        return self.getresp()

    def voidcmd(self, cmd):
        """Send a command and expect a response beginning with '2'."""
        self.putcmd(cmd)
        return self.voidresp()

    def sendport(self, host, port):
        '''Send a PORT command with the current host and the given
        port number.
        '''
        hbytes = host.split('.')
        pbytes = [repr(port//256), repr(port%256)]
        bytes = hbytes + pbytes
        cmd = 'PORT ' + ','.join(bytes)
        return self.voidcmd(cmd)

    def sendeprt(self, host, port):
        '''Send an EPRT command with the current host and the given port number.'''
        af = 0
        if self.af == socket.AF_INET:
            af = 1
        if self.af == socket.AF_INET6:
            af = 2
        if af == 0:
            raise error_proto('unsupported address family')
        fields = ['', repr(af), host, repr(port), '']
        cmd = 'EPRT ' + '|'.join(fields)
        return self.voidcmd(cmd)

    def makeport(self):
        '''Create a new socket and send a PORT command for it.'''
        sock = socket.create_server(("", 0), family=self.af, backlog=1)
        port = sock.getsockname()[1] # Get proper port
        host = self.sock.getsockname()[0] # Get proper host
        if self.af == socket.AF_INET:
            resp = self.sendport(host, port)
        else:
            resp = self.sendeprt(host, port)
        if self.timeout is not _GLOBAL_DEFAULT_TIMEOUT:
            sock.settimeout(self.timeout)
        return sock

    def makepasv(self):
        """Internal: Does the PASV or EPSV handshake -> (address, port)"""
        if self.af == socket.AF_INET:
            untrusted_host, port = parse227(self.sendcmd('PASV'))
            if self.trust_server_pasv_ipv4_address:
                host = untrusted_host
            else:
                host = self.sock.getpeername()[0]
        else:
            host, port = parse229(self.sendcmd('EPSV'), self.sock.getpeername())
        return host, port

    def ntransfercmd(self, cmd, rest=None):
        """Initiate a transfer over the data connection.

        If the transfer is active, send a port command and the
        transfer command, and accept the connection.  If the server is
        passive, send a pasv command, connect to it, and start the
        transfer command.  Either way, return the socket for the
        connection and the expected size of the transfer.  The
        expected size may be None if it could not be determined.

        Optional 'rest' argument can be a string that is sent as the
        argument to a REST command.  This is essentially a server
        marker used to tell the server to skip over any data up to the
        given marker.
        """
        size = None
        if self.passiveserver:
            host, port = self.makepasv()
            conn = socket.create_connection((host, port), self.timeout,
                                            source_address=self.source_address)
            try:
                if rest is not None:
                    self.sendcmd("REST %s" % rest)
                resp = self.sendcmd(cmd)
                # Some servers apparently send a 200 reply to
                # a LIST or STOR command, before the 150 reply
                # (and way before the 226 reply). This seems to
                # be in violation of the protocol (which only allows
                # 1xx or error messages for LIST), so we just discard
                # this response.
                if resp[0] == '2':
                    resp = self.getresp()
                if resp[0] != '1':
                    raise error_reply(resp)
            except:
                conn.close()
                raise
        else:
            with self.makeport() as sock:
                if rest is not None:
                    self.sendcmd("REST %s" % rest)
                resp = self.sendcmd(cmd)
                # See above.
                if resp[0] == '2':
                    resp = self.getresp()
                if resp[0] != '1':
                    raise error_reply(resp)
                conn, sockaddr = sock.accept()
                if self.timeout is not _GLOBAL_DEFAULT_TIMEOUT:
                    conn.settimeout(self.timeout)
        if resp[:3] == '150':
            # this is conditional in case we received a 125
            size = parse150(resp)
        return conn, size

    def transfercmd(self, cmd, rest=None):
        """Like ntransfercmd() but returns only the socket."""
        return self.ntransfercmd(cmd, rest)[0]

    def login(self, user = '', passwd = '', acct = ''):
        '''Login, default anonymous.'''
        if not user:
            user = 'anonymous'
        if not passwd:
            passwd = ''
        if not acct:
            acct = ''
        if user == 'anonymous' and passwd in {'', '-'}:
            # If there is no anonymous ftp password specified
            # then we'll just use anonymous@
            # We don't send any other thing because:
            # - We want to remain anonymous
            # - We want to stop SPAM
            # - We don't want to let ftp sites to discriminate by the user,
            #   host or country.
            passwd = passwd + 'anonymous@'
        resp = self.sendcmd('USER ' + user)
        if resp[0] == '3':
            resp = self.sendcmd('PASS ' + passwd)
        if resp[0] == '3':
            resp = self.sendcmd('ACCT ' + acct)
        if resp[0] != '2':
            raise error_reply(resp)
        return resp

    def retrbinary(self, cmd, callback, blocksize=8192, rest=None):
        """Retrieve data in binary mode.  A new port is created for you.

        Args:
          cmd: A RETR command.
          callback: A single parameter callable to be called on each
                    block of data read.
          blocksize: The maximum number of bytes to read from the
                     socket at one time.  [default: 8192]
          rest: Passed to transfercmd().  [default: None]

        Returns:
          The response code.
        """
        self.voidcmd('TYPE I')
        with self.transfercmd(cmd, rest) as conn:
            while data := conn.recv(blocksize):
                callback(data)
            # shutdown ssl layer
            if _SSLSocket is not None and isinstance(conn, _SSLSocket):
                conn.unwrap()
        return self.voidresp()

    def retrlines(self, cmd, callback = None):
        """Retrieve data in line mode.  A new port is created for you.

        Args:
          cmd: A RETR, LIST, or NLST command.
          callback: An optional single parameter callable that is called
                    for each line with the trailing CRLF stripped.
                    [default: print_line()]

        Returns:
          The response code.
        """
        if callback is None:
            callback = print_line
        resp = self.sendcmd('TYPE A')
        with self.transfercmd(cmd) as conn, \
                 conn.makefile('r', encoding=self.encoding) as fp:
            while 1:
                line = fp.readline(self.maxline + 1)
                if len(line) > self.maxline:
                    raise Error("got more than %d bytes" % self.maxline)
                if self.debugging > 2:
                    print('*retr*', repr(line))
                if not line:
                    break
                if line[-2:] == CRLF:
                    line = line[:-2]
                elif line[-1:] == '\n':
                    line = line[:-1]
                callback(line)
            # shutdown ssl layer
            if _SSLSocket is not None and isinstance(conn, _SSLSocket):
                conn.unwrap()
        return self.voidresp()

    def storbinary(self, cmd, fp, blocksize=8192, callback=None, rest=None):
        """Store a file in binary mode.  A new port is created for you.

        Args:
          cmd: A STOR command.
          fp: A file-like object with a read(num_bytes) method.
          blocksize: The maximum data size to read from fp and send over
                     the connection at once.  [default: 8192]
          callback: An optional single parameter callable that is called on
                    each block of data after it is sent.  [default: None]
          rest: Passed to transfercmd().  [default: None]

        Returns:
          The response code.
        """
        self.voidcmd('TYPE I')
        with self.transfercmd(cmd, rest) as conn:
            while buf := fp.read(blocksize):
                conn.sendall(buf)
                if callback:
                    callback(buf)
            # shutdown ssl layer
            if _SSLSocket is not None and isinstance(conn, _SSLSocket):
                conn.unwrap()
        return self.voidresp()

    def storlines(self, cmd, fp, callback=None):
        """Store a file in line mode.  A new port is created for you.

        Args:
          cmd: A STOR command.
          fp: A file-like object with a readline() method.
          callback: An optional single parameter callable that is called on
                    each line after it is sent.  [default: None]

        Returns:
          The response code.
        """
        self.voidcmd('TYPE A')
        with self.transfercmd(cmd) as conn:
            while 1:
                buf = fp.readline(self.maxline + 1)
                if len(buf) > self.maxline:
                    raise Error("got more than %d bytes" % self.maxline)
                if not buf:
                    break
                if buf[-2:] != B_CRLF:
                    if buf[-1] in B_CRLF: buf = buf[:-1]
                    buf = buf + B_CRLF
                conn.sendall(buf)
                if callback:
                    callback(buf)
            # shutdown ssl layer
            if _SSLSocket is not None and isinstance(conn, _SSLSocket):
                conn.unwrap()
        return self.voidresp()

    def acct(self, password):
        '''Send new account name.'''
        cmd = 'ACCT ' + password
        return self.voidcmd(cmd)

    def nlst(self, *args):
        '''Return a list of files in a given directory (default the current).'''
        cmd = 'NLST'
        for arg in args:
            cmd = cmd + (' ' + arg)
        files = []
        self.retrlines(cmd, files.append)
        return files

    def dir(self, *args):
        '''List a directory in long form.
        By default list current directory to stdout.
        Optional last argument is callback function; all
        non-empty arguments before it are concatenated to the
        LIST command.  (This *should* only be used for a pathname.)'''
        cmd = 'LIST'
        func = None
        if args[-1:] and not isinstance(args[-1], str):
            args, func = args[:-1], args[-1]
        for arg in args:
            if arg:
                cmd = cmd + (' ' + arg)
        self.retrlines(cmd, func)

    def mlsd(self, path="", facts=[]):
        '''List a directory in a standardized format by using MLSD
        command (RFC-3659). If path is omitted the current directory
        is assumed. "facts" is a list of strings representing the type
        of information desired (e.g. ["type", "size", "perm"]).

        Return a generator object yielding a tuple of two elements
        for every file found in path.
        First element is the file name, the second one is a dictionary
        including a variable number of "facts" depending on the server
        and whether "facts" argument has been provided.
        '''
        if facts:
            self.sendcmd("OPTS MLST " + ";".join(facts) + ";")
        if path:
            cmd = "MLSD %s" % path
        else:
            cmd = "MLSD"
        lines = []
        self.retrlines(cmd, lines.append)
        for line in lines:
            facts_found, _, name = line.rstrip(CRLF).partition(' ')
            entry = {}
            for fact in facts_found[:-1].split(";"):
                key, _, value = fact.partition("=")
                entry[key.lower()] = value
            yield (name, entry)

    def rename(self, fromname, toname):
        '''Rename a file.'''
        resp = self.sendcmd('RNFR ' + fromname)
        if resp[0] != '3':
            raise error_reply(resp)
        return self.voidcmd('RNTO ' + toname)

    def delete(self, filename):
        '''Delete a file.'''
        resp = self.sendcmd('DELE ' + filename)
        if resp[:3] in {'250', '200'}:
            return resp
        else:
            raise error_reply(resp)

    def cwd(self, dirname):
        '''Change to a directory.'''
        if dirname == '..':
            try:
                return self.voidcmd('CDUP')
            except error_perm as msg:
                if msg.args[0][:3] != '500':
                    raise
        elif dirname == '':
            dirname = '.'  # does nothing, but could return error
        cmd = 'CWD ' + dirname
        return self.voidcmd(cmd)

    def size(self, filename):
        '''Retrieve the size of a file.'''
        # The SIZE command is defined in RFC-3659
        resp = self.sendcmd('SIZE ' + filename)
        if resp[:3] == '213':
            s = resp[3:].strip()
            return int(s)

    def mkd(self, dirname):
        '''Make a directory, return its full pathname.'''
        resp = self.voidcmd('MKD ' + dirname)
        # fix around non-compliant implementations such as IIS shipped
        # with Windows server 2003
        if not resp.startswith('257'):
            return ''
        return parse257(resp)

    def rmd(self, dirname):
        '''Remove a directory.'''
        return self.voidcmd('RMD ' + dirname)

    def pwd(self):
        '''Return current working directory.'''
        resp = self.voidcmd('PWD')
        # fix around non-compliant implementations such as IIS shipped
        # with Windows server 2003
        if not resp.startswith('257'):
            return ''
        return parse257(resp)

    def quit(self):
        '''Quit, and close the connection.'''
        resp = self.voidcmd('QUIT')
        self.close()
        return resp

    def close(self):
        '''Close the connection without assuming anything about it.'''
        try:
            file = self.file
            self.file = None
            if file is not None:
                file.close()
        finally:
            sock = self.sock
            self.sock = None
            if sock is not None:
                sock.close()

try:
    import ssl
except ImportError:
    _SSLSocket = None
else:
    _SSLSocket = ssl.SSLSocket

    class FTP_TLS(FTP):
        '''A FTP subclass which adds TLS support to FTP as described
        in RFC-4217.

        Connect as usual to port 21 implicitly securing the FTP control
        connection before authenticating.

        Securing the data connection requires user to explicitly ask
        for it by calling prot_p() method.

        Usage example:
        >>> from ftplib import FTP_TLS
        >>> ftps = FTP_TLS('ftp.python.org')
        >>> ftps.login()  # login anonymously previously securing control channel
        '230 Guest login ok, access restrictions apply.'
        >>> ftps.prot_p()  # switch to secure data connection
        '200 Protection level set to P'
        >>> ftps.retrlines('LIST')  # list directory content securely
        total 9
        drwxr-xr-x   8 root     wheel        1024 Jan  3  1994 .
        drwxr-xr-x   8 root     wheel        1024 Jan  3  1994 ..
        drwxr-xr-x   2 root     wheel        1024 Jan  3  1994 bin
        drwxr-xr-x   2 root     wheel        1024 Jan  3  1994 etc
        d-wxrwxr-x   2 ftp      wheel        1024 Sep  5 13:43 incoming
        drwxr-xr-x   2 root     wheel        1024 Nov 17  1993 lib
        drwxr-xr-x   6 1094     wheel        1024 Sep 13 19:07 pub
        drwxr-xr-x   3 root     wheel        1024 Jan  3  1994 usr
        -rw-r--r--   1 root     root          312 Aug  1  1994 welcome.msg
        '226 Transfer complete.'
        >>> ftps.quit()
        '221 Goodbye.'
        >>>
        '''

        def __init__(self, host='', user='', passwd='', acct='',
                     *, context=None, timeout=_GLOBAL_DEFAULT_TIMEOUT,
                     source_address=None, encoding='utf-8'):
            if context is None:
                context = ssl._create_stdlib_context()
            self.context = context
            self._prot_p = False
            super().__init__(host, user, passwd, acct,
                             timeout, source_address, encoding=encoding)

        def login(self, user='', passwd='', acct='', secure=True):
            if secure and not isinstance(self.sock, ssl.SSLSocket):
                self.auth()
            return super().login(user, passwd, acct)

        def auth(self):
            '''Set up secure control connection by using TLS/SSL.'''
            if isinstance(self.sock, ssl.SSLSocket):
                raise ValueError("Already using TLS")
            if self.context.protocol >= ssl.PROTOCOL_TLS:
                resp = self.voidcmd('AUTH TLS')
            else:
                resp = self.voidcmd('AUTH SSL')
            self.sock = self.context.wrap_socket(self.sock, server_hostname=self.host)
            self.file = self.sock.makefile(mode='r', encoding=self.encoding)
            return resp

        def ccc(self):
            '''Switch back to a clear-text control connection.'''
            if not isinstance(self.sock, ssl.SSLSocket):
                raise ValueError("not using TLS")
            resp = self.voidcmd('CCC')
            self.sock = self.sock.unwrap()
            return resp

        def prot_p(self):
            '''Set up secure data connection.'''
            # PROT defines whether or not the data channel is to be protected.
            # Though RFC-2228 defines four possible protection levels,
            # RFC-4217 only recommends two, Clear and Private.
            # Clear (PROT C) means that no security is to be used on the
            # data-channel, Private (PROT P) means that the data-channel
            # should be protected by TLS.
            # PBSZ command MUST still be issued, but must have a parameter of
            # '0' to indicate that no buffering is taking place and the data
            # connection should not be encapsulated.
            self.voidcmd('PBSZ 0')
            resp = self.voidcmd('PROT P')
            self._prot_p = True
            return resp

        def prot_c(self):
            '''Set up clear text data connection.'''
            resp = self.voidcmd('PROT C')
            self._prot_p = False
            return resp

        # --- Overridden FTP methods

        def ntransfercmd(self, cmd, rest=None):
            conn, size = super().ntransfercmd(cmd, rest)
            if self._prot_p:
                conn = self.context.wrap_socket(conn,
                                                server_hostname=self.host)
            return conn, size

        def abort(self):
            # overridden as we can't pass MSG_OOB flag to sendall()
            line = b'ABOR' + B_CRLF
            self.sock.sendall(line)
            resp = self.getmultiline()
            if resp[:3] not in {'426', '225', '226'}:
                raise error_proto(resp)
            return resp

    __all__.append('FTP_TLS')
    all_errors = (Error, OSError, EOFError, ssl.SSLError)


_150_re = None

def parse150(resp):
    '''Parse the '150' response for a RETR request.
    Returns the expected transfer size or None; size is not guaranteed to
    be present in the 150 message.
    '''
    if resp[:3] != '150':
        raise error_reply(resp)
    global _150_re
    if _150_re is None:
        import re
        _150_re = re.compile(
            r"150 .* \((\d+) bytes\)", re.IGNORECASE | re.ASCII)
    m = _150_re.match(resp)
    if not m:
        return None
    return int(m.group(1))


_227_re = None

def parse227(resp):
    '''Parse the '227' response for a PASV request.
    Raises error_proto if it does not contain '(h1,h2,h3,h4,p1,p2)'
    Return ('host.addr.as.numbers', port#) tuple.'''
    if resp[:3] != '227':
        raise error_reply(resp)
    global _227_re
    if _227_re is None:
        import re
        _227_re = re.compile(r'(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)', re.ASCII)
    m = _227_re.search(resp)
    if not m:
        raise error_proto(resp)
    numbers = m.groups()
    host = '.'.join(numbers[:4])
    port = (int(numbers[4]) << 8) + int(numbers[5])
    return host, port


def parse229(resp, peer):
    '''Parse the '229' response for an EPSV request.
    Raises error_proto if it does not contain '(|||port|)'
    Return ('host.addr.as.numbers', port#) tuple.'''
    if resp[:3] != '229':
        raise error_reply(resp)
    left = resp.find('(')
    if left < 0: raise error_proto(resp)
    right = resp.find(')', left + 1)
    if right < 0:
        raise error_proto(resp) # should contain '(|||port|)'
    if resp[left + 1] != resp[right - 1]:
        raise error_proto(resp)
    parts = resp[left + 1:right].split(resp[left+1])
    if len(parts) != 5:
        raise error_proto(resp)
    host = peer[0]
    port = int(parts[3])
    return host, port


def parse257(resp):
    '''Parse the '257' response for a MKD or PWD request.
    This is a response to a MKD or PWD request: a directory name.
    Returns the directoryname in the 257 reply.'''
    if resp[:3] != '257':
        raise error_reply(resp)
    if resp[3:5] != ' "':
        return '' # Not compliant to RFC 959, but UNIX ftpd does this
    dirname = ''
    i = 5
    n = len(resp)
    while i < n:
        c = resp[i]
        i = i+1
        if c == '"':
            if i >= n or resp[i] != '"':
                break
            i = i+1
        dirname = dirname + c
    return dirname


def print_line(line):
    '''Default retrlines callback to print a line.'''
    print(line)


def ftpcp(source, sourcename, target, targetname = '', type = 'I'):
    '''Copy file from one FTP-instance to another.'''
    if not targetname:
        targetname = sourcename
    type = 'TYPE ' + type
    source.voidcmd(type)
    target.voidcmd(type)
    # Don't trust the IPv4 address the source server advertises in its PASV
    # reply: a malicious source could otherwise point the target's data
    # connection at an arbitrary host (SSRF).  A caller that needs the old
    # behavior can set trust_server_pasv_ipv4_address on the source FTP
    # object.  See FTP.makepasv(), which applies the same rule.
    untrusted_host, sourceport = parse227(source.sendcmd('PASV'))
    if source.trust_server_pasv_ipv4_address:
        sourcehost = untrusted_host
    else:
        sourcehost = source.sock.getpeername()[0]
    target.sendport(sourcehost, sourceport)
    # RFC 959: the user must "listen" [...] BEFORE sending the
    # transfer request.
    # So: STOR before RETR, because here the target is a "user".
    treply = target.sendcmd('STOR ' + targetname)
    if treply[:3] not in {'125', '150'}:
        raise error_proto  # RFC 959
    sreply = source.sendcmd('RETR ' + sourcename)
    if sreply[:3] not in {'125', '150'}:
        raise error_proto  # RFC 959
    source.voidresp()
    target.voidresp()


def test():
    '''Test program.
    Usage: ftplib [-d] [-r[file]] host [-l[dir]] [-d[dir]] [-p] [file] ...

    Options:
      -d        increase debugging level
      -r[file]  set alternate ~/.netrc file

    Commands:
      -l[dir]   list directory
      -d[dir]   change the current directory
      -p        toggle passive and active mode
      file      retrieve the file and write it to stdout
    '''

    if len(sys.argv) < 2:
        print(test.__doc__)
        sys.exit(0)

    import netrc

    debugging = 0
    rcfile = None
    while sys.argv[1] == '-d':
        debugging = debugging+1
        del sys.argv[1]
    if sys.argv[1][:2] == '-r':
        # get name of alternate ~/.netrc file:
        rcfile = sys.argv[1][2:]
        del sys.argv[1]
    host = sys.argv[1]
    ftp = FTP(host)
    ftp.set_debuglevel(debugging)
    userid = passwd = acct = ''
    try:
        netrcobj = netrc.netrc(rcfile)
    except OSError:
        if rcfile is not None:
            print("Could not open account file -- using anonymous login.",
                  file=sys.stderr)
    else:
        try:
            userid, acct, passwd = netrcobj.authenticators(host)
        except (KeyError, TypeError):
            # no account for host
            print("No account -- using anonymous login.", file=sys.stderr)
    ftp.login(userid, passwd, acct)
    for file in sys.argv[2:]:
        if file[:2] == '-l':
            ftp.dir(file[2:])
        elif file[:2] == '-d':
            cmd = 'CWD'
            if file[2:]: cmd = cmd + ' ' + file[2:]
            resp = ftp.sendcmd(cmd)
        elif file == '-p':
            ftp.set_pasv(not ftp.passiveserver)
        else:
            ftp.retrbinary('RETR ' + file, \
                           sys.stdout.buffer.write, 1024)
            sys.stdout.buffer.flush()
        sys.stdout.flush()
    ftp.quit()


if __name__ == '__main__':
    test()
````

### ПУТЬ: Python/pythoncore-3.14-64/Lib/functools.py (1165 строк, 44729 байт)

````python
"""functools.py - Tools for working with functions and callable objects
"""
# Python module wrapper for _functools C module
# to allow utilities written in Python to be added
# to the functools module.
# Written by Nick Coghlan <ncoghlan at gmail.com>,
# Raymond Hettinger <python at rcn.com>,
# and Łukasz Langa <lukasz at langa.pl>.
#   Copyright (C) 2006 Python Software Foundation.
# See C source code for _functools credits/copyright

__all__ = ['update_wrapper', 'wraps', 'WRAPPER_ASSIGNMENTS', 'WRAPPER_UPDATES',
           'total_ordering', 'cache', 'cmp_to_key', 'lru_cache', 'reduce',
           'partial', 'partialmethod', 'singledispatch', 'singledispatchmethod',
           'cached_property', 'Placeholder']

from abc import get_cache_token
from collections import namedtuple
# import weakref  # Deferred to single_dispatch()
from operator import itemgetter
from reprlib import recursive_repr
from types import GenericAlias, MethodType, MappingProxyType, UnionType
from _thread import RLock

################################################################################
### update_wrapper() and wraps() decorator
################################################################################

# update_wrapper() and wraps() are tools to help write
# wrapper functions that can handle naive introspection

WRAPPER_ASSIGNMENTS = ('__module__', '__name__', '__qualname__', '__doc__',
                       '__annotate__', '__type_params__')
WRAPPER_UPDATES = ('__dict__',)
def update_wrapper(wrapper,
                   wrapped,
                   assigned = WRAPPER_ASSIGNMENTS,
                   updated = WRAPPER_UPDATES):
    """Update a wrapper function to look like the wrapped function

       wrapper is the function to be updated
       wrapped is the original function
       assigned is a tuple naming the attributes assigned directly
       from the wrapped function to the wrapper function (defaults to
       functools.WRAPPER_ASSIGNMENTS)
       updated is a tuple naming the attributes of the wrapper that
       are updated with the corresponding attribute from the wrapped
       function (defaults to functools.WRAPPER_UPDATES)
    """
    for attr in assigned:
        try:
            value = getattr(wrapped, attr)
        except AttributeError:
            pass
        else:
            setattr(wrapper, attr, value)
    for attr in updated:
        getattr(wrapper, attr).update(getattr(wrapped, attr, {}))
    # Issue #17482: set __wrapped__ last so we don't inadvertently copy it
    # from the wrapped function when updating __dict__
    wrapper.__wrapped__ = wrapped
    # Return the wrapper so this can be used as a decorator via partial()
    return wrapper

def wraps(wrapped,
          assigned = WRAPPER_ASSIGNMENTS,
          updated = WRAPPER_UPDATES):
    """Decorator factory to apply update_wrapper() to a wrapper function

       Returns a decorator that invokes update_wrapper() with the decorated
       function as the wrapper argument and the arguments to wraps() as the
       remaining arguments. Default arguments are as for update_wrapper().
       This is a convenience function to simplify applying partial() to
       update_wrapper().
    """
    return partial(update_wrapper, wrapped=wrapped,
                   assigned=assigned, updated=updated)


################################################################################
### total_ordering class decorator
################################################################################

# The total ordering functions all invoke the root magic method directly
# rather than using the corresponding operator.  This avoids possible
# infinite recursion that could occur when the operator dispatch logic
# detects a NotImplemented result and then calls a reflected method.

def _gt_from_lt(self, other):
    'Return a > b.  Computed by @total_ordering from (not a < b) and (a != b).'
    op_result = type(self).__lt__(self, other)
    if op_result is NotImplemented:
        return op_result
    return not op_result and self != other

def _le_from_lt(self, other):
    'Return a <= b.  Computed by @total_ordering from (a < b) or (a == b).'
    op_result = type(self).__lt__(self, other)
    if op_result is NotImplemented:
        return op_result
    return op_result or self == other

def _ge_from_lt(self, other):
    'Return a >= b.  Computed by @total_ordering from (not a < b).'
    op_result = type(self).__lt__(self, other)
    if op_result is NotImplemented:
        return op_result
    return not op_result

def _ge_from_le(self, other):
    'Return a >= b.  Computed by @total_ordering from (not a <= b) or (a == b).'
    op_result = type(self).__le__(self, other)
    if op_result is NotImplemented:
        return op_result
    return not op_result or self == other

def _lt_from_le(self, other):
    'Return a < b.  Computed by @total_ordering from (a <= b) and (a != b).'
    op_result = type(self).__le__(self, other)
    if op_result is NotImplemented:
        return op_result
    return op_result and self != other

def _gt_from_le(self, other):
    'Return a > b.  Computed by @total_ordering from (not a <= b).'
    op_result = type(self).__le__(self, other)
    if op_result is NotImplemented:
        return op_result
    return not op_result

def _lt_from_gt(self, other):
    'Return a < b.  Computed by @total_ordering from (not a > b) and (a != b).'
    op_result = type(self).__gt__(self, other)
    if op_result is NotImplemented:
        return op_result
    return not op_result and self != other

def _ge_from_gt(self, other):
    'Return a >= b.  Computed by @total_ordering from (a > b) or (a == b).'
    op_result = type(self).__gt__(self, other)
    if op_result is NotImplemented:
        return op_result
    return op_result or self == other

def _le_from_gt(self, other):
    'Return a <= b.  Computed by @total_ordering from (not a > b).'
    op_result = type(self).__gt__(self, other)
    if op_result is NotImplemented:
        return op_result
    return not op_result

def _le_from_ge(self, other):
    'Return a <= b.  Computed by @total_ordering from (not a >= b) or (a == b).'
    op_result = type(self).__ge__(self, other)
    if op_result is NotImplemented:
        return op_result
    return not op_result or self == other

def _gt_from_ge(self, other):
    'Return a > b.  Computed by @total_ordering from (a >= b) and (a != b).'
    op_result = type(self).__ge__(self, other)
    if op_result is NotImplemented:
        return op_result
    return op_result and self != other

def _lt_from_ge(self, other):
    'Return a < b.  Computed by @total_ordering from (not a >= b).'
    op_result = type(self).__ge__(self, other)
    if op_result is NotImplemented:
        return op_result
    return not op_result

_convert = {
    '__lt__': [('__gt__', _gt_from_lt),
               ('__le__', _le_from_lt),
               ('__ge__', _ge_from_lt)],
    '__le__': [('__ge__', _ge_from_le),
               ('__lt__', _lt_from_le),
               ('__gt__', _gt_from_le)],
    '__gt__': [('__lt__', _lt_from_gt),
               ('__ge__', _ge_from_gt),
               ('__le__', _le_from_gt)],
    '__ge__': [('__le__', _le_from_ge),
               ('__gt__', _gt_from_ge),
               ('__lt__', _lt_from_ge)]
}

def total_ordering(cls):
    """Class decorator that fills in missing ordering methods"""
    # Find user-defined comparisons (not those inherited from object).
    roots = {op for op in _convert if getattr(cls, op, None) is not getattr(object, op, None)}
    if not roots:
        raise ValueError('must define at least one ordering operation: < > <= >=')
    root = max(roots)       # prefer __lt__ to __le__ to __gt__ to __ge__
    for opname, opfunc in _convert[root]:
        if opname not in roots:
            opfunc.__name__ = opname
            setattr(cls, opname, opfunc)
    return cls


################################################################################
### cmp_to_key() function converter
################################################################################

def cmp_to_key(mycmp):
    """Convert a cmp= function into a key= function"""
    class K(object):
        __slots__ = ['obj']
        def __init__(self, obj):
            self.obj = obj
        def __lt__(self, other):
            return mycmp(self.obj, other.obj) < 0
        def __gt__(self, other):
            return mycmp(self.obj, other.obj) > 0
        def __eq__(self, other):
            return mycmp(self.obj, other.obj) == 0
        def __le__(self, other):
            return mycmp(self.obj, other.obj) <= 0
        def __ge__(self, other):
            return mycmp(self.obj, other.obj) >= 0
        __hash__ = None
    return K

try:
    from _functools import cmp_to_key
except ImportError:
    pass


################################################################################
### reduce() sequence to a single item
################################################################################

_initial_missing = object()

def reduce(function, sequence, initial=_initial_missing):
    """
    reduce(function, iterable, /[, initial]) -> value

    Apply a function of two arguments cumulatively to the items of an iterable, from left to right.

    This effectively reduces the iterable to a single value.  If initial is present,
    it is placed before the items of the iterable in the calculation, and serves as
    a default when the iterable is empty.

    For example, reduce(lambda x, y: x+y, [1, 2, 3, 4, 5])
    calculates ((((1 + 2) + 3) + 4) + 5).
    """

    it = iter(sequence)

    if initial is _initial_missing:
        try:
            value = next(it)
        except StopIteration:
            raise TypeError(
                "reduce() of empty iterable with no initial value") from None
    else:
        value = initial

    for element in it:
        value = function(value, element)

    return value


################################################################################
### partial() argument application
################################################################################


class _PlaceholderType:
    """The type of the Placeholder singleton.

    Used as a placeholder for partial arguments.
    """
    __instance = None
    __slots__ = ()

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"type '{cls.__name__}' is not an acceptable base type")

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = object.__new__(cls)
        return cls.__instance

    def __repr__(self):
        return 'Placeholder'

    def __reduce__(self):
        return 'Placeholder'

Placeholder = _PlaceholderType()

def _partial_prepare_merger(args):
    if not args:
        return 0, None
    nargs = len(args)
    order = []
    j = nargs
    for i, a in enumerate(args):
        if a is Placeholder:
            order.append(j)
            j += 1
        else:
            order.append(i)
    phcount = j - nargs
    merger = itemgetter(*order) if phcount else None
    return phcount, merger

def _partial_new(cls, func, /, *args, **keywords):
    if issubclass(cls, partial):
        base_cls = partial
        if not callable(func):
            raise TypeError("the first argument must be callable")
    else:
        base_cls = partialmethod
        # func could be a descriptor like classmethod which isn't callable
        if not callable(func) and not hasattr(func, "__get__"):
            raise TypeError(f"the first argument {func!r} must be a callable "
                            "or a descriptor")
    if args and args[-1] is Placeholder:
        raise TypeError("trailing Placeholders are not allowed")
    for value in keywords.values():
        if value is Placeholder:
            raise TypeError("Placeholder cannot be passed as a keyword argument")
    if isinstance(func, base_cls):
        pto_phcount = func._phcount
        tot_args = func.args
        if args:
            tot_args += args
            if pto_phcount:
                # merge args with args of `func` which is `partial`
                nargs = len(args)
                if nargs < pto_phcount:
                    tot_args += (Placeholder,) * (pto_phcount - nargs)
                tot_args = func._merger(tot_args)
                if nargs > pto_phcount:
                    tot_args += args[pto_phcount:]
            phcount, merger = _partial_prepare_merger(tot_args)
        else:   # works for both pto_phcount == 0 and != 0
            phcount, merger = pto_phcount, func._merger
        keywords = {**func.keywords, **keywords}
        func = func.func
    else:
        tot_args = args
        phcount, merger = _partial_prepare_merger(tot_args)

    self = object.__new__(cls)
    self.func = func
    self.args = tot_args
    self.keywords = keywords
    self._phcount = phcount
    self._merger = merger
    return self

def _partial_repr(self):
    cls = type(self)
    module = cls.__module__
    qualname = cls.__qualname__
    args = [repr(self.func)]
    args.extend(map(repr, self.args))
    args.extend(f"{k}={v!r}" for k, v in self.keywords.items())
    return f"{module}.{qualname}({', '.join(args)})"

# Purely functional, no descriptor behaviour
class partial:
    """New function with partial application of the given arguments
    and keywords.
    """

    __slots__ = ("func", "args", "keywords", "_phcount", "_merger",
                 "__dict__", "__weakref__")

    __new__ = _partial_new
    __repr__ = recursive_repr()(_partial_repr)

    def __call__(self, /, *args, **keywords):
        phcount = self._phcount
        if phcount:
            try:
                pto_args = self._merger(self.args + args)
                args = args[phcount:]
            except IndexError:
                raise TypeError("missing positional arguments "
                                "in 'partial' call; expected "
                                f"at least {phcount}, got {len(args)}")
        else:
            pto_args = self.args
        keywords = {**self.keywords, **keywords}
        return self.func(*pto_args, *args, **keywords)

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return MethodType(self, obj)

    def __reduce__(self):
        return type(self), (self.func,), (self.func, self.args,
               self.keywords or None, self.__dict__ or None)

    def __setstate__(self, state):
        if not isinstance(state, tuple):
            raise TypeError("argument to __setstate__ must be a tuple")
        if len(state) != 4:
            raise TypeError(f"expected 4 items in state, got {len(state)}")
        func, args, kwds, namespace = state
        if (not callable(func) or not isinstance(args, tuple) or
           (kwds is not None and not isinstance(kwds, dict)) or
           (namespace is not None and not isinstance(namespace, dict))):
            raise TypeError("invalid partial state")

        if args and args[-1] is Placeholder:
            raise TypeError("trailing Placeholders are not allowed")
        phcount, merger = _partial_prepare_merger(args)

        args = tuple(args) # just in case it's a subclass
        if kwds is None:
            kwds = {}
        elif type(kwds) is not dict: # XXX does it need to be *exactly* dict?
            kwds = dict(kwds)
        if namespace is None:
            namespace = {}

        self.__dict__ = namespace
        self.func = func
        self.args = args
        self.keywords = kwds
        self._phcount = phcount
        self._merger = merger

    __class_getitem__ = classmethod(GenericAlias)


try:
    from _functools import partial, Placeholder, _PlaceholderType
except ImportError:
    pass

# Descriptor version
class partialmethod:
    """Method descriptor with partial application of the given arguments
    and keywords.

    Supports wrapping existing descriptors and handles non-descriptor
    callables as instance methods.
    """
    __new__ = _partial_new
    __repr__ = _partial_repr

    def _make_unbound_method(self):
        def _method(cls_or_self, /, *args, **keywords):
            phcount = self._phcount
            if phcount:
                try:
                    pto_args = self._merger(self.args + args)
                    args = args[phcount:]
                except IndexError:
                    raise TypeError("missing positional arguments "
                                    "in 'partialmethod' call; expected "
                                    f"at least {phcount}, got {len(args)}")
            else:
                pto_args = self.args
            keywords = {**self.keywords, **keywords}
            return self.func(cls_or_self, *pto_args, *args, **keywords)
        _method.__isabstractmethod__ = self.__isabstractmethod__
        _method.__partialmethod__ = self
        return _method

    def __get__(self, obj, cls=None):
        get = getattr(self.func, "__get__", None)
        result = None
        if get is not None:
            new_func = get(obj, cls)
            if new_func is not self.func:
                # Assume __get__ returning something new indicates the
                # creation of an appropriate callable
                result = partial(new_func, *self.args, **self.keywords)
                try:
                    result.__self__ = new_func.__self__
                except AttributeError:
                    pass
        if result is None:
            # If the underlying descriptor didn't do anything, treat this
            # like an instance method
            result = self._make_unbound_method().__get__(obj, cls)
        return result

    @property
    def __isabstractmethod__(self):
        return getattr(self.func, "__isabstractmethod__", False)

    __class_getitem__ = classmethod(GenericAlias)


# Helper functions

def _unwrap_partial(func):
    while isinstance(func, partial):
        func = func.func
    return func

def _unwrap_partialmethod(func):
    prev = None
    while func is not prev:
        prev = func
        while isinstance(getattr(func, "__partialmethod__", None), partialmethod):
            func = func.__partialmethod__
        while isinstance(func, partialmethod):
            func = getattr(func, 'func')
        func = _unwrap_partial(func)
    return func

################################################################################
### LRU Cache function decorator
################################################################################

_CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])

def _make_key(args, kwds, typed,
             kwd_mark = (object(),),
             fasttypes = {int, str},
             tuple=tuple, type=type, len=len):
    """Make a cache key from optionally typed positional and keyword arguments

    The key is constructed in a way that is flat as possible rather than
    as a nested structure that would take more memory.

    If there is only a single argument and its data type is known to cache
    its hash value, then that argument is returned without a wrapper.  This
    saves space and improves lookup speed.

    """
    # All of code below relies on kwds preserving the order input by the user.
    # Formerly, we sorted() the kwds before looping.  The new way is *much*
    # faster; however, it means that f(x=1, y=2) will now be treated as a
    # distinct call from f(y=2, x=1) which will be cached separately.
    key = args
    if kwds:
        key += kwd_mark
        for item in kwds.items():
            key += item
    if typed:
        key += tuple(type(v) for v in args)
        if kwds:
            key += tuple(type(v) for v in kwds.values())
    elif len(key) == 1 and type(key[0]) in fasttypes:
        return key[0]
    return key

def lru_cache(maxsize=128, typed=False):
    """Least-recently-used cache decorator.

    If *maxsize* is set to None, the LRU features are disabled and the cache
    can grow without bound.

    If *typed* is True, arguments of different types will be cached
    separately.  For example, f(decimal.Decimal("3.0")) and f(3.0) will be
    treated as distinct calls with distinct results.  Some types such as
    str and int may be cached separately even when typed is false.

    Arguments to the cached function must be hashable.

    View the cache statistics named tuple (hits, misses, maxsize, currsize)
    with f.cache_info().  Clear the cache and statistics with
    f.cache_clear().  Access the underlying function with f.__wrapped__.

    See:  https://en.wikipedia.org/wiki/Cache_replacement_policies#Least_recently_used_(LRU)

    """

    # Users should only access the lru_cache through its public API:
    #       cache_info, cache_clear, and f.__wrapped__
    # The internals of the lru_cache are encapsulated for thread safety and
    # to allow the implementation to change (including a possible C version).

    if isinstance(maxsize, int):
        # Negative maxsize is treated as 0
        if maxsize < 0:
            maxsize = 0
    elif callable(maxsize) and isinstance(typed, bool):
        # The user_function was passed in directly via the maxsize argument
        user_function, maxsize = maxsize, 128
        wrapper = _lru_cache_wrapper(user_function, maxsize, typed, _CacheInfo)
        wrapper.cache_parameters = lambda : {'maxsize': maxsize, 'typed': typed}
        return update_wrapper(wrapper, user_function)
    elif maxsize is not None:
        raise TypeError(
            'Expected first argument to be an integer, a callable, or None')

    def decorating_function(user_function):
        wrapper = _lru_cache_wrapper(user_function, maxsize, typed, _CacheInfo)
        wrapper.cache_parameters = lambda : {'maxsize': maxsize, 'typed': typed}
        return update_wrapper(wrapper, user_function)

    return decorating_function

def _lru_cache_wrapper(user_function, maxsize, typed, _CacheInfo):
    # Constants shared by all lru cache instances:
    sentinel = object()          # unique object used to signal cache misses
    make_key = _make_key         # build a key from the function arguments
    PREV, NEXT, KEY, RESULT = 0, 1, 2, 3   # names for the link fields

    cache = {}
    hits = misses = 0
    full = False
    cache_get = cache.get    # bound method to lookup a key or return None
    cache_len = cache.__len__  # get cache size without calling len()
    lock = RLock()           # because linkedlist updates aren't threadsafe
    root = []                # root of the circular doubly linked list
    root[:] = [root, root, None, None]     # initialize by pointing to self

    if maxsize == 0:

        def wrapper(*args, **kwds):
            # No caching -- just a statistics update
            nonlocal misses
            misses += 1
            result = user_function(*args, **kwds)
            return result

    elif maxsize is None:

        def wrapper(*args, **kwds):
            # Simple caching without ordering or size limit
            nonlocal hits, misses
            key = make_key(args, kwds, typed)
            result = cache_get(key, sentinel)
            if result is not sentinel:
                hits += 1
                return result
            misses += 1
            result = user_function(*args, **kwds)
            cache[key] = result
            return result

    else:

        def wrapper(*args, **kwds):
            # Size limited caching that tracks accesses by recency
            nonlocal root, hits, misses, full
            key = make_key(args, kwds, typed)
            with lock:
                link = cache_get(key)
                if link is not None:
                    # Move the link to the front of the circular queue
                    link_prev, link_next, _key, result = link
                    link_prev[NEXT] = link_next
                    link_next[PREV] = link_prev
                    last = root[PREV]
                    last[NEXT] = root[PREV] = link
                    link[PREV] = last
                    link[NEXT] = root
                    hits += 1
                    return result
                misses += 1
            result = user_function(*args, **kwds)
            with lock:
                if key in cache:
                    # Getting here means that this same key was added to the
                    # cache while the lock was released.  Since the link
                    # update is already done, we need only return the
                    # computed result and update the count of misses.
                    pass
                elif full:
                    # Use the old root to store the new key and result.
                    oldroot = root
                    oldroot[KEY] = key
                    oldroot[RESULT] = result
                    # Empty the oldest link and make it the new root.
                    # Keep a reference to the old key and old result to
                    # prevent their ref counts from going to zero during the
                    # update. That will prevent potentially arbitrary object
                    # clean-up code (i.e. __del__) from running while we're
                    # still adjusting the links.
                    root = oldroot[NEXT]
                    oldkey = root[KEY]
                    oldresult = root[RESULT]
                    root[KEY] = root[RESULT] = None
                    # Now update the cache dictionary.
                    del cache[oldkey]
                    # Save the potentially reentrant cache[key] assignment
                    # for last, after the root and links have been put in
                    # a consistent state.
                    cache[key] = oldroot
                else:
                    # Put result in a new link at the front of the queue.
                    last = root[PREV]
                    link = [last, root, key, result]
                    last[NEXT] = root[PREV] = cache[key] = link
                    # Use the cache_len bound method instead of the len() function
                    # which could potentially be wrapped in an lru_cache itself.
                    full = (cache_len() >= maxsize)
            return result

    def cache_info():
        """Report cache statistics"""
        with lock:
            return _CacheInfo(hits, misses, maxsize, cache_len())

    def cache_clear():
        """Clear the cache and cache statistics"""
        nonlocal hits, misses, full
        with lock:
            cache.clear()
            root[:] = [root, root, None, None]
            hits = misses = 0
            full = False

    wrapper.cache_info = cache_info
    wrapper.cache_clear = cache_clear
    return wrapper

try:
    from _functools import _lru_cache_wrapper
except ImportError:
    pass


################################################################################
### cache -- simplified access to the infinity cache
################################################################################

def cache(user_function, /):
    'Simple lightweight unbounded cache.  Sometimes called "memoize".'
    return lru_cache(maxsize=None)(user_function)


################################################################################
### singledispatch() - single-dispatch generic function decorator
################################################################################

def _c3_merge(sequences):
    """Merges MROs in *sequences* to a single MRO using the C3 algorithm.

    Adapted from https://docs.python.org/3/howto/mro.html.

    """
    result = []
    while True:
        sequences = [s for s in sequences if s]   # purge empty sequences
        if not sequences:
            return result
        for s1 in sequences:   # find merge candidates among seq heads
            candidate = s1[0]
            for s2 in sequences:
                if candidate in s2[1:]:
                    candidate = None
                    break      # reject the current head, it appears later
            else:
                break
        if candidate is None:
            raise RuntimeError("Inconsistent hierarchy")
        result.append(candidate)
        # remove the chosen candidate
        for seq in sequences:
            if seq[0] == candidate:
                del seq[0]

def _c3_mro(cls, abcs=None):
    """Computes the method resolution order using extended C3 linearization.

    If no *abcs* are given, the algorithm works exactly like the built-in C3
    linearization used for method resolution.

    If given, *abcs* is a list of abstract base classes that should be inserted
    into the resulting MRO. Unrelated ABCs are ignored and don't end up in the
    result. The algorithm inserts ABCs where their functionality is introduced,
    i.e. issubclass(cls, abc) returns True for the class itself but returns
    False for all its direct base classes. Implicit ABCs for a given class
    (either registered or inferred from the presence of a special method like
    __len__) are inserted directly after the last ABC explicitly listed in the
    MRO of said class. If two implicit ABCs end up next to each other in the
    resulting MRO, their ordering depends on the order of types in *abcs*.

    """
    for i, base in enumerate(reversed(cls.__bases__)):
        if hasattr(base, '__abstractmethods__'):
            boundary = len(cls.__bases__) - i
            break   # Bases up to the last explicit ABC are considered first.
    else:
        boundary = 0
    abcs = list(abcs) if abcs else []
    explicit_bases = list(cls.__bases__[:boundary])
    abstract_bases = []
    other_bases = list(cls.__bases__[boundary:])
    for base in abcs:
        if issubclass(cls, base) and not any(
                issubclass(b, base) for b in cls.__bases__
            ):
            # If *cls* is the class that introduces behaviour described by
            # an ABC *base*, insert said ABC to its MRO.
            abstract_bases.append(base)
    for base in abstract_bases:
        abcs.remove(base)
    explicit_c3_mros = [_c3_mro(base, abcs=abcs) for base in explicit_bases]
    abstract_c3_mros = [_c3_mro(base, abcs=abcs) for base in abstract_bases]
    other_c3_mros = [_c3_mro(base, abcs=abcs) for base in other_bases]
    return _c3_merge(
        [[cls]] +
        explicit_c3_mros + abstract_c3_mros + other_c3_mros +
        [explicit_bases] + [abstract_bases] + [other_bases]
    )

def _compose_mro(cls, types):
    """Calculates the method resolution order for a given class *cls*.

    Includes relevant abstract base classes (with their respective bases) from
    the *types* iterable. Uses a modified C3 linearization algorithm.

    """
    bases = set(cls.__mro__)
    # Remove entries which are already present in the __mro__ or unrelated.
    def is_related(typ):
        return (typ not in bases and hasattr(typ, '__mro__')
                                 and not isinstance(typ, GenericAlias)
                                 and issubclass(cls, typ))
    types = [n for n in types if is_related(n)]
    # Remove entries which are strict bases of other entries (they will end up
    # in the MRO anyway.
    def is_strict_base(typ):
        for other in types:
            if typ != other and typ in other.__mro__:
                return True
        return False
    types = [n for n in types if not is_strict_base(n)]
    # Subclasses of the ABCs in *types* which are also implemented by
    # *cls* can be used to stabilize ABC ordering.
    type_set = set(types)
    mro = []
    for typ in types:
        found = []
        for sub in typ.__subclasses__():
            if sub not in bases and issubclass(cls, sub):
                found.append([s for s in sub.__mro__ if s in type_set])
        if not found:
            mro.append(typ)
            continue
        # Favor subclasses with the biggest number of useful bases
        found.sort(key=len, reverse=True)
        for sub in found:
            for subcls in sub:
                if subcls not in mro:
                    mro.append(subcls)
    return _c3_mro(cls, abcs=mro)

def _find_impl(cls, registry):
    """Returns the best matching implementation from *registry* for type *cls*.

    Where there is no registered implementation for a specific type, its method
    resolution order is used to find a more generic implementation.

    Note: if *registry* does not contain an implementation for the base
    *object* type, this function may return None.

    """
    mro = _compose_mro(cls, registry.keys())
    match = None
    for t in mro:
        if match is not None:
            # If *match* is an implicit ABC but there is another unrelated,
            # equally matching implicit ABC, refuse the temptation to guess.
            if (t in registry and t not in cls.__mro__
                              and match not in cls.__mro__
                              and not issubclass(match, t)):
                raise RuntimeError("Ambiguous dispatch: {} or {}".format(
                    match, t))
            break
        if t in registry:
            match = t
    return registry.get(match)

def singledispatch(func):
    """Single-dispatch generic function decorator.

    Transforms a function into a generic function, which can have different
    behaviours depending upon the type of its first argument. The decorated
    function acts as the default implementation, and additional
    implementations can be registered using the register() attribute of the
    generic function.
    """
    # There are many programs that use functools without singledispatch, so we
    # trade-off making singledispatch marginally slower for the benefit of
    # making start-up of such applications slightly faster.
    import weakref

    registry = {}
    dispatch_cache = weakref.WeakKeyDictionary()
    cache_token = None

    def dispatch(cls):
        """generic_func.dispatch(cls) -> <function implementation>

        Runs the dispatch algorithm to return the best available implementation
        for the given *cls* registered on *generic_func*.

        """
        nonlocal cache_token
        if cache_token is not None:
            current_token = get_cache_token()
            if cache_token != current_token:
                dispatch_cache.clear()
                cache_token = current_token
        try:
            impl = dispatch_cache[cls]
        except KeyError:
            try:
                impl = registry[cls]
            except KeyError:
                impl = _find_impl(cls, registry)
            dispatch_cache[cls] = impl
        return impl

    def _is_valid_dispatch_type(cls):
        if isinstance(cls, type):
            return True
        return (isinstance(cls, UnionType) and
                all(isinstance(arg, type) for arg in cls.__args__))

    def register(cls, func=None):
        """generic_func.register(cls, func) -> func

        Registers a new implementation for the given *cls* on a *generic_func*.

        """
        nonlocal cache_token
        if _is_valid_dispatch_type(cls):
            if func is None:
                return lambda f: register(cls, f)
        else:
            if func is not None:
                raise TypeError(
                    f"Invalid first argument to `register()`. "
                    f"{cls!r} is not a class or union type."
                )
            ann = getattr(cls, '__annotate__', None)
            if ann is None:
                raise TypeError(
                    f"Invalid first argument to `register()`: {cls!r}. "
                    f"Use either `@register(some_class)` or plain `@register` "
                    f"on an annotated function."
                )
            func = cls

            # only import typing if annotation parsing is necessary
            from typing import get_type_hints
            from annotationlib import Format, ForwardRef
            argname, cls = next(iter(get_type_hints(func, format=Format.FORWARDREF).items()))
            if not _is_valid_dispatch_type(cls):
                if isinstance(cls, UnionType):
                    raise TypeError(
                        f"Invalid annotation for {argname!r}. "
                        f"{cls!r} not all arguments are classes."
                    )
                elif isinstance(cls, ForwardRef):
                    raise TypeError(
                        f"Invalid annotation for {argname!r}. "
                        f"{cls!r} is an unresolved forward reference."
                    )
                else:
                    raise TypeError(
                        f"Invalid annotation for {argname!r}. "
                        f"{cls!r} is not a class."
                    )

        if isinstance(cls, UnionType):
            for arg in cls.__args__:
                registry[arg] = func
        else:
            registry[cls] = func
        if cache_token is None and hasattr(cls, '__abstractmethods__'):
            cache_token = get_cache_token()
        dispatch_cache.clear()
        return func

    def wrapper(*args, **kw):
        if not args:
            raise TypeError(f'{funcname} requires at least '
                            '1 positional argument')
        return dispatch(args[0].__class__)(*args, **kw)

    funcname = getattr(func, '__name__', 'singledispatch function')
    registry[object] = func
    wrapper.register = register
    wrapper.dispatch = dispatch
    wrapper.registry = MappingProxyType(registry)
    wrapper._clear_cache = dispatch_cache.clear
    update_wrapper(wrapper, func)
    return wrapper


# Descriptor version
class singledispatchmethod:
    """Single-dispatch generic method descriptor.

    Supports wrapping existing descriptors.
    """

    def __init__(self, func):
        if not callable(func) and not hasattr(func, "__get__"):
            raise TypeError(f"{func!r} is not callable or a descriptor")

        self.dispatcher = singledispatch(func)
        self.func = func

    def register(self, cls, method=None):
        """generic_method.register(cls, func) -> func

        Registers a new implementation for the given *cls* on a *generic_method*.
        """
        return self.dispatcher.register(cls, func=method)

    def __get__(self, obj, cls=None):
        return _singledispatchmethod_get(self, obj, cls)

    @property
    def __isabstractmethod__(self):
        return getattr(self.func, '__isabstractmethod__', False)

    def __repr__(self):
        try:
            name = self.func.__qualname__
        except AttributeError:
            try:
                name = self.func.__name__
            except AttributeError:
                name = '?'
        return f'<single dispatch method descriptor {name}>'

class _singledispatchmethod_get:
    def __init__(self, unbound, obj, cls):
        self._unbound = unbound
        self._dispatch = unbound.dispatcher.dispatch
        self._obj = obj
        self._cls = cls
        # Set instance attributes which cannot be handled in __getattr__()
        # because they conflict with type descriptors.
        func = unbound.func
        try:
            self.__module__ = func.__module__
        except AttributeError:
            pass
        try:
            self.__doc__ = func.__doc__
        except AttributeError:
            pass

    def __repr__(self):
        try:
            name = self.__qualname__
        except AttributeError:
            try:
                name = self.__name__
            except AttributeError:
                name = '?'
        if self._obj is not None:
            return f'<bound single dispatch method {name} of {self._obj!r}>'
        else:
            return f'<single dispatch method {name}>'

    def __call__(self, /, *args, **kwargs):
        if not args:
            funcname = getattr(self._unbound.func, '__name__',
                               'singledispatchmethod method')
            raise TypeError(f'{funcname} requires at least '
                            '1 positional argument')
        return self._dispatch(args[0].__class__).__get__(self._obj, self._cls)(*args, **kwargs)

    def __getattr__(self, name):
        # Resolve these attributes lazily to speed up creation of
        # the _singledispatchmethod_get instance.
        if name not in {'__name__', '__qualname__', '__isabstractmethod__',
                        '__annotations__', '__type_params__'}:
            raise AttributeError
        return getattr(self._unbound.func, name)

    @property
    def __wrapped__(self):
        return self._unbound.func

    @property
    def register(self):
        return self._unbound.register


################################################################################
### cached_property() - property result cached as instance attribute
################################################################################

_NOT_FOUND = object()

class cached_property:
    def __init__(self, func):
        self.func = func
        self.attrname = None
        self.__doc__ = func.__doc__
        self.__module__ = func.__module__

    def __set_name__(self, owner, name):
        if self.attrname is None:
            self.attrname = name
        elif name != self.attrname:
            raise TypeError(
                "Cannot assign the same cached_property to two different names "
                f"({self.attrname!r} and {name!r})."
            )

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        if self.attrname is None:
            raise TypeError(
                "Cannot use cached_property instance without calling __set_name__ on it.")
        try:
            cache = instance.__dict__
        except AttributeError:  # not all objects have __dict__ (e.g. class defines slots)
            msg = (
                f"No '__dict__' attribute on {type(instance).__name__!r} "
                f"instance to cache {self.attrname!r} property."
            )
            raise TypeError(msg) from None
        val = cache.get(self.attrname, _NOT_FOUND)
        if val is _NOT_FOUND:
            val = self.func(instance)
            try:
                cache[self.attrname] = val
            except TypeError:
                msg = (
                    f"The '__dict__' attribute on {type(instance).__name__!r} instance "
                    f"does not support item assignment for caching {self.attrname!r} property."
                )
                raise TypeError(msg) from None
        return val

    __class_getitem__ = classmethod(GenericAlias)

def _warn_python_reduce_kwargs(py_reduce):
    @wraps(py_reduce)
    def wrapper(*args, **kwargs):
        if 'function' in kwargs or 'sequence' in kwargs:
            import os
            import warnings
            warnings.warn(
                'Calling functools.reduce with keyword arguments '
                '"function" or "sequence" '
                'is deprecated in Python 3.14 and will be '
                'forbidden in Python 3.16.',
                DeprecationWarning,
                skip_file_prefixes=(os.path.dirname(__file__),))
        return py_reduce(*args, **kwargs)
    return wrapper

reduce = _warn_python_reduce_kwargs(reduce)
del _warn_python_reduce_kwargs

# The import of the C accelerated version of reduce() has been moved
# here due to gh-121676. In Python 3.16, _warn_python_reduce_kwargs()
# should be removed and the import block should be moved back right
# after the definition of reduce().
try:
    from _functools import reduce
except ImportError:
    pass
````

### ПУТЬ: README.md (115 строк, 6718 байт)

````markdown
# LocalComet / LocalAgent

Локальный Python-агент с маршрутизацией команд, планированием, выполнением через LLM и браузерной автоматизацией.

## Архитектура

```
user input
    │
    ▼
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Router  │────▶│ Planner  │────▶│ Executor │
│(core/)   │     │(core/)   │     │(core/)   │
└──────────┘     └──────────┘     └──────────┘
                                       │
                                       ▼
                                 ┌──────────┐
                                 │  Agents  │
                                 │(agents/) │
                                 └──────────┘
                                       │
                                       ▼
                                 ┌──────────┐
                                 │ Modules  │
                                 │(modules/)│
                                 └──────────┘
```

**Поток выполнения:**

1. **Router** (`core/router.py`) — определяет категорию команды (system, browser, code, file, windows и др.)
2. **Planner** (`core/planner.py`) — генерирует JSON-план действий через LLM
3. **Executor** (`core/executor.py`) — диспетчеризует план в соответствующий агент
4. **Agents** (`agents/`) — тонкие адаптеры, делегируют работу в modules
5. **Modules** (`modules/`) — реальная логика: браузер, ChatGPT relay, self-edit, автоматизация, диагностика

**LLM-доступ:** `core/llm.py` — LM Studio (локально) или OpenAI API (конфигурация в `config.py`).

**Состояние:** `core/state.py` + `memory/state.json` — персистентное хранилище ключ-значение.

**Workflow патчинга:** `request.md → response.json → validate → apply → after patch`

## Запуск

```powershell
# Основной консольный интерфейс (v5/v6)
python -m next.app_v5

# Tkinter-панель управления
python LocalComet_Control_Panel.py

# Патч-панель
python LocalComet_Patch_Panel.py
```

### Конфигурация

`config.py`:
- `LMSTUDIO_API` — эндпоинт LM Studio (по умолчанию `http://127.0.0.1:1234/v1/chat/completions`)
- `MODEL` — локальная модель (по умолчанию `qwen3-14b`)
- `OPENAI_MODEL` — модель OpenAI для relay
- `OPENAI_RESPONSES_API` — эндпоинт OpenAI Responses API

## Тестирование

```powershell
# Синтаксическая проверка изменённых файлов
python -m py_compile path/to/file.py

# Тесты моделей
python tools/model_tester.py
python tools/hard_model_tester.py

# Проверка GPT-моста
python tools/test_gpt_bridge.py

# Регрессионные тесты
python tools/test_v677_regression.py
python tools/test_v678_router_registry.py

# Stability test (через консоль)
# Ввести: stability test

# Полные flow-тесты
python test_full_flow.py
python test_full_flow2.py
python test_full_flow3.py
```

## Структура проекта

| Директория | Назначение |
|---|---|
| `agents/` | Тонкие агент-адаптеры. Каждый агент реализует `handle(action, data)` и делегирует работу в `modules/`. Включает: browser, code, file, operator, project, research, windows, system, workspace, diagnostics, history, maintenance, self_edit, gpt, chatgpt_relay, stability, automation, gpt_browser. |
| `core/` | Ядро оркестрации: маршрутизация (`router.py`), планирование через LLM (`planner.py`), выполнение (`executor.py`), доступ к LLM (`llm.py`), состояние (`state.py`), агентский цикл (`loop.py`), контекст проекта (`project_context.py`). |
| `modules/` | Реализация всей функциональности: браузерная автоматизация (browser*, computer_use_*), ChatGPT relay, self-edit, автоматизация, диагностика, workspace, отчёты, голосовое управление, knowledge-система, desktop-интеграция. ~140 модулей. |
| `next/` | Консольный интерфейс нового поколения (v5/v6): `app_v5.py` — главный цикл с shortcut-маппингом, `goal_manager.py` — анализ целей, `task_planner.py` — декомпозиция задач, `task_queue.py` — очередь задач, `observer.py` — наблюдение за страницей. |
| `desktop/` | Desktop-приложение на Tauri + SvelteKit: контракты IPC (`contracts/`), Rust-бэкенд и фронтенд (`localcomet-desktop/`). Управление артефактами, runtime-каталог, model-каталог. |
| `tools/` | Утилиты и тесты: тестеры моделей, GPT-bridge проверки, регрессионные тесты (v677–v6846), аудит-бандлы, preflight-проверки, инсталлятор, dev-лаунчер. |
| `scripts/` | Вспомогательные скрипты: генерация runtime-манифеста, ручной запуск model gateway. |

### Дополнительные файлы

| Файл | Назначение |
|---|---|
| `app.py` | Старый агентский цикл (legacy) |
| `agent.py` | Базовый агент-интерфейс |
| `config.py` | Конфигурация LLM-эндпоинтов |
| `LocalComet_Control_Panel.py` | Tkinter GUI панель управления |
| `LocalComet_Patch_Panel.py` | Панель применения патчей |
| `GenerateCapabilityMap.py` | Генерация карты возможностей |
| `memory/state.json` | Персистентное состояние агента |
| `Projects/` | Runtime-данные, отчёты, браузерный профиль |
| `docs/` | Архитектурная документация |
| `third_party/` | Сторонние зависимости |
````

### ПУТЬ: response.json (82 строк, 6209 байт)

````json
{
  "task": "Анализ архитектуры: определение старой/новой структуры, план работы для команды из 10 агентов.",
  "status": "done",
  "architecture_analysis": {
    "old_architecture": {
      "entry": "app.py (LocalComet v3 — Agent Loop)",
      "folders": ["agents/", "core/", "modules/"],
      "description": "Классический pipeline route→plan→execute. agents/ — 18 тонких адаптеров handle(action, data). core/ — роутер, планировщик, исполнитель, цикл, состояние. modules/ — 140+ файлов реализации."
    },
    "new_architecture": {
      "entry": "next/app_v5.py (LocalComet v6.02 - Command Center)",
      "folders": ["next/", "desktop/", "tools/", "scripts/"],
      "description": "next/ — новая оркестрация: goal_manager, task_planner, task_queue, observer. desktop/ — десктопное приложение + IPC-контракты. tools/ — 47 тестов и утилит. scripts/ — генерация манифеста, проверка паритета команд."
    },
    "shared_layer": ["core/", "modules/"],
    "note": "core/ и modules/ используются обеими архитектурами. next/ импортирует core/ напрямую."
  },
  "team_plan": {
    "agent_01_architect": {
      "role": "Архитектор",
      "task": "Разорвать циклическую зависимость core ↔ modules. Вынести core.state в common/state_store.py. Убрать импорты core.router/planner/executor из modules.",
      "files": ["core/state.py", "core/router.py", "core/planner.py", "core/executor.py"],
      "priority": "P1"
    },
    "agent_02_refactor_app": {
      "role": "Рефакторинг app_v5",
      "task": "Декомпозировать next/app_v5.py (2039 строк). Заменить 12 функций _run_direct_* на реестр команд core/commands.py. Перенести SHORTCUTS в core/router.",
      "files": ["next/app_v5.py", "core/router.py"],
      "priority": "P2"
    },
    "agent_03_god_modules": {
      "role": "Декомпозиция god-модулей",
      "task": "Разделить: premium_task_panel_ru (2957), desktop_control_plane_ru (2208), computer_use_contract_tests_ru (1818), local_model_gateway_ru (1811), stability_test (1664).",
      "files": ["modules/premium_task_panel_ru.py", "modules/desktop_control_plane_ru.py", "modules/stability_test.py"],
      "priority": "P3"
    },
    "agent_04_security": {
      "role": "Безопасность и легаси",
      "task": "Рефакторить agent.py (shell-инъекция в search_web, хардкод LLM URL). Заменить app.py на заглушку-редирект к next/app_v5. Убрать 5 агентов, импортирующих core.state напрямую.",
      "files": ["agent.py", "app.py", "agents/browser_agent.py", "agents/code_agent.py", "agents/project_agent.py", "agents/system_agent.py", "agents/windows_agent.py"],
      "priority": "P4"
    },
    "agent_05_testing": {
      "role": "Тестирование",
      "task": "Расширить покрытие в tools/. Добавить интеграционные тесты для next/task_planner, next/goal_manager. Создать pytest-совместимый runner. Покрыть regression_commands и auto_verification.",
      "files": ["tools/", "tests/", "modules/stability_test.py"],
      "priority": "P2"
    },
    "agent_06_desktop": {
      "role": "Десктоп",
      "task": "Развитие desktop/: IPC-контракты, sidecar runtime, control plane. Синхронизация с modules/desktop_control_plane_ru и modules/desktop_sidecar_runtime_ru.",
      "files": ["desktop/", "modules/desktop_control_plane_ru.py", "modules/desktop_sidecar_runtime_ru.py"],
      "priority": "P3"
    },
    "agent_07_browser": {
      "role": "Браузерная автоматизация",
      "task": "Консолидация 10+ browser_* модулей в единый фасад modules/browser_facade.py. Устранение дублирования между browser_direct, browser_autopilot, browser_super, browser_operator.",
      "files": ["modules/browser_direct.py", "modules/browser_autopilot.py", "modules/browser_super.py", "modules/browser_operator.py", "modules/browser_actions.py"],
      "priority": "P3"
    },
    "agent_08_knowledge": {
      "role": "Система знаний",
      "task": "Унификация knowledge_* модулей (11 файлов). Единый knowledge_pipeline: proposal → review → decision → injection. Интеграция с core/state.",
      "files": ["modules/knowledge_adapter_ru.py", "modules/knowledge_change_proposal_ru.py", "modules/knowledge_change_review_ru.py", "modules/knowledge_injection_ru.py", "modules/knowledge_contract_ru.py"],
      "priority": "P3"
    },
    "agent_09_ui": {
      "role": "UI и Control Panel",
      "task": "Стабилизация LocalComet_Control_Panel.py. Интеграция premium_ui_* модулей. Убрать дублирование между premium_native_ui_ru, premium_ui_now, premium_ui_prototype.",
      "files": ["LocalComet_Control_Panel.py", "modules/premium_native_ui_ru.py", "modules/premium_ui_now.py", "modules/command_center_ui.py"],
      "priority": "P4"
    },
    "agent_10_docs_ci": {
      "role": "Документация и CI",
      "task": "Обновить docs/. Создать docs/engineering/adr-002-target-architecture.md. Настроить GitHub Actions для py_compile + tools/ тестов. Обновить README.md.",
      "files": ["docs/", ".github/", "README.md", "scripts/"],
      "priority": "P2"
    }
  },
  "execution_order": ["agent_01_architect", "agent_02_refactor_app", "agent_04_security", "agent_05_testing", "agent_10_docs_ci", "agent_03_god_modules", "agent_06_desktop", "agent_07_browser", "agent_08_knowledge", "agent_09_ui"],
  "docs_page": "docs/team_plan_10_agents.md"
}
````

### ПУТЬ: scripts/check_command_parity.py (93 строк, 2630 байт)

````python
"""Command parity gate for LocalComet desktop.

Verifies that every Tauri command registered in generate_handler![]
has a corresponding invoke() call in the Svelte frontend, and vice versa.

Exit codes:
  0 - parity holds
  1 - mismatch detected
  2 - could not parse sources
"""

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LIB_RS = REPO_ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "src" / "lib.rs"
SRC_DIR = REPO_ROOT / "desktop" / "localcomet-desktop" / "src"


def extract_registered_commands(lib_rs_text: str) -> set[str]:
    match = re.search(
        r"generate_handler!\[(.*?)\]", lib_rs_text, re.DOTALL
    )
    if not match:
        return set()
    body = match.group(1)
    return {
        name.strip()
        for name in body.split(",")
        if name.strip() and not name.strip().startswith("//")
    }


def extract_frontend_invokes(src_dir: pathlib.Path) -> set[str]:
    invokes = set()
    pattern = re.compile(
        r"""(?:invoke\w*)\s*(?:<[^>]*>)?\(\s*["']([a-z_]+)["']"""
    )
    for ts_file in src_dir.rglob("*.ts"):
        text = ts_file.read_text(encoding="utf-8", errors="replace")
        invokes.update(pattern.findall(text))
    for svelte_file in src_dir.rglob("*.svelte"):
        text = svelte_file.read_text(encoding="utf-8", errors="replace")
        invokes.update(pattern.findall(text))
    return invokes


def main() -> int:
    if not LIB_RS.exists():
        print(f"FAIL: cannot find {LIB_RS}")
        return 2

    lib_text = LIB_RS.read_text(encoding="utf-8", errors="replace")
    registered = extract_registered_commands(lib_text)

    if not registered:
        print("FAIL: no commands found in generate_handler!")
        return 2

    if not SRC_DIR.is_dir():
        print(f"FAIL: cannot find {SRC_DIR}")
        return 2

    invoked = extract_frontend_invokes(SRC_DIR)

    registered_not_invoked = registered - invoked
    invoked_not_registered = invoked - registered

    errors = []
    for cmd in sorted(registered_not_invoked):
        errors.append(f"REGISTERED_NOT_INVOKED: {cmd}")
    for cmd in sorted(invoked_not_registered):
        errors.append(f"INVOKED_NOT_REGISTERED: {cmd}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(
            f"\n{len(registered)} registered, {len(invoked)} invoked, "
            f"{len(errors)} mismatch(es)"
        )
        return 1

    print(
        f"OK: {len(registered)} commands registered and invoked "
        f"(parity holds)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
````

### ПУТЬ: scripts/check_evidence_provenance.py (85 строк, 2930 байт)

````python
"""Verify LocalComet evidence provenance.

For every artifacts/evidence/*.txt file:
  - require a complete provenance header (command, exit_code, tree_digest,
    body_sha256);
  - recompute the current source tree digest;
  - report STALE if the recorded tree_digest no longer matches (sources changed
    after the evidence was captured);
  - report BODY_MISMATCH if the recorded body_sha256 does not match the body.

Exit 0 if all evidence is fresh and intact, 1 otherwise.

Injection: modify any source file covered by refresh_evidence.SOURCE_GLOBS
without re-running refresh_evidence.py -> this gate exits 1 (STALE).
"""

import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from refresh_evidence import EVIDENCE_DIR, tree_digest  # noqa: E402

REQUIRED_FIELDS = ("command", "exit_code", "tree_digest", "body_sha256")


def parse_evidence(text: str):
    if "\n---\n" not in text:
        return None, None
    header_part, body = text.split("\n---\n", 1)
    fields = {}
    for line in header_part.split("\n"):
        if line.startswith("# ") and ":" in line:
            key, _, value = line[2:].partition(":")
            fields[key.strip()] = value.strip()
    return fields, body


def main() -> int:
    if not EVIDENCE_DIR.is_dir():
        print(f"FAIL: evidence directory missing: {EVIDENCE_DIR}")
        return 1

    evidence_files = sorted(EVIDENCE_DIR.glob("*.txt"))
    if not evidence_files:
        print("FAIL: no evidence files found (run scripts/refresh_evidence.py)")
        return 1

    current_digest = tree_digest()
    errors = []

    for path in evidence_files:
        text = path.read_text(encoding="utf-8")
        fields, body = parse_evidence(text)
        if fields is None:
            errors.append(f"MISSING_PROVENANCE: {path.name} has no provenance header")
            continue
        for field in REQUIRED_FIELDS:
            if field not in fields:
                errors.append(f"MISSING_FIELD: {path.name} lacks '{field}'")
        if "tree_digest" in fields and fields["tree_digest"] != current_digest:
            errors.append(
                f"STALE: {path.name} tree_digest {fields['tree_digest'][:16]}... "
                f"!= current {current_digest[:16]}..."
            )
        if "body_sha256" in fields and body is not None:
            actual = hashlib.sha256(body.encode("utf-8")).hexdigest()
            if actual != fields["body_sha256"]:
                errors.append(f"BODY_MISMATCH: {path.name} body hash changed")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"\n{len(errors)} provenance problem(s) across {len(evidence_files)} file(s)")
        return 1

    print(
        f"OK: {len(evidence_files)} evidence file(s) fresh and intact "
        f"(tree={current_digest[:16]}...)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
````

### ПУТЬ: scripts/check_real_sidecar_tests.py (76 строк, 2504 байт)

````python
"""Real-sidecar test honesty gate (Task D).

The real-sidecar integration tests in supervisor.rs skip via early return when
LOCALCOMET_TEST_PROJECT_ROOT / LOCALCOMET_TEST_PYTHON are absent. With
LOCALCOMET_REQUIRE_REAL_SIDECAR set (CI, after installing the sidecar) that
skip becomes a panic, so the suite count can no longer silently include
not-actually-run tests.

This gate enforces the CI contract:
  - Only meaningful when LOCALCOMET_REQUIRE_REAL_SIDECAR is set.
  - Runs the test suite and fails if any test is reported "ignored" or if the
    require-environment panic fired (meaning the sidecar was not installed
    before cargo test).

Exit 0 = contract holds, 1 = violation, 2 = could not run.

CI usage:
  set LOCALCOMET_REQUIRE_REAL_SIDECAR=1
  python scripts/check_real_sidecar_tests.py
"""

import os
import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CARGO_MANIFEST = REPO_ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "Cargo.toml"


def main() -> int:
    if os.environ.get("LOCALCOMET_REQUIRE_REAL_SIDECAR") is None:
        print(
            "SKIP: LOCALCOMET_REQUIRE_REAL_SIDECAR not set; gate only enforces in "
            "require mode (CI). Real-sidecar tests skip honestly with a notice."
        )
        return 0

    result = subprocess.run(
        ["cargo", "test", "--manifest-path", str(CARGO_MANIFEST)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or "") + (result.stderr or "")

    problems = []

    ignored = re.search(r"(\d+) ignored", output)
    if ignored and int(ignored.group(1)) > 0:
        problems.append(f"{ignored.group(1)} test(s) reported ignored under require mode")

    if "LOCALCOMET_REQUIRE_REAL_SIDECAR is set but the real-sidecar environment" in output:
        problems.append(
            "real-sidecar tests panicked: sidecar environment missing "
            "(install the sidecar and set LOCALCOMET_TEST_PROJECT_ROOT / "
            "LOCALCOMET_TEST_PYTHON before cargo test)"
        )

    if result.returncode != 0 and not problems:
        problems.append(f"cargo test exited {result.returncode}")

    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1

    print("OK: real-sidecar tests ran under require mode with no silent skips")
    return 0


if __name__ == "__main__":
    sys.exit(main())
````

### ПУТЬ: scripts/check_tool_risk_registry.py (158 строк, 5199 байт)

````python
"""Tool risk registry gate for LocalComet.

Introspects the REAL console-agent filesystem operations in modules/files.py
and verifies each is classified in security/invariants/tool_risk_levels.toml.

A "tool function" is any top-level function in modules/files.py whose body
calls safe_path() (the Projects/ confinement helper). safe_path() itself is
excluded because its body does not call safe_path().

A tool function is "mutating" if its body performs a filesystem mutation
(write_text, mkdir, unlink, rmtree, shutil.move/copy).

Rules enforced:
  1. Every tool function has a registry entry (implementation = "...::<fn>").
  2. Every mutating tool function has requires_approval = true.
  3. Every mutating tool function has risk_level in {guarded, dangerous}.
  4. Every registry entry has a valid risk_level.

Exit codes:
  0 - registry covers all real tool functions and rules hold
  1 - violation detected
  2 - could not read/parse inputs

Injection: add a new mutating function to modules/files.py that calls
safe_path() but is absent from the TOML -> this gate exits 1.
"""

import pathlib
import re
import sys

try:
    import tomllib
except ImportError:  # pragma: no cover
    print("FAIL: tomllib unavailable (Python >= 3.11 required)")
    sys.exit(2)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES_PY = REPO_ROOT / "modules" / "files.py"
REGISTRY = REPO_ROOT / "security" / "invariants" / "tool_risk_levels.toml"

VALID_RISK_LEVELS = {"read_only", "guarded", "dangerous"}
MUTATION_MARKERS = (
    "write_text",
    ".mkdir(",
    ".unlink(",
    "rmtree",
    "shutil.move",
    "shutil.copy",
)


def parse_top_level_functions(source: str) -> dict:
    """Return {function_name: body_text} for top-level defs."""
    functions = {}
    current_name = None
    current_body = []
    for line in source.split("\n"):
        match = re.match(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
        if match:
            if current_name is not None:
                functions[current_name] = "\n".join(current_body)
            current_name = match.group(1)
            current_body = []
        elif current_name is not None:
            current_body.append(line)
    if current_name is not None:
        functions[current_name] = "\n".join(current_body)
    return functions


def main() -> int:
    if not FILES_PY.exists():
        print(f"FAIL: cannot find {FILES_PY}")
        return 2
    if not REGISTRY.exists():
        print(f"FAIL: cannot find {REGISTRY}")
        return 2

    source = FILES_PY.read_text(encoding="utf-8")
    functions = parse_top_level_functions(source)

    tool_functions = {
        name: body
        for name, body in functions.items()
        if "safe_path(" in body
    }
    mutating_functions = {
        name
        for name, body in tool_functions.items()
        if any(marker in body for marker in MUTATION_MARKERS)
    }

    try:
        registry = tomllib.loads(REGISTRY.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        print(f"FAIL: registry is not valid TOML: {exc}")
        return 2

    tools = registry.get("tools", [])
    if not isinstance(tools, list) or not tools:
        print("FAIL: registry has no [[tools]] entries")
        return 1

    errors = []

    impl_to_entry = {}
    for entry in tools:
        name = entry.get("name")
        risk = entry.get("risk_level")
        impl = entry.get("implementation", "")
        requires = entry.get("requires_approval")
        if risk not in VALID_RISK_LEVELS:
            errors.append(f"INVALID_RISK_LEVEL: {name} -> {risk!r}")
        if not isinstance(requires, bool):
            errors.append(f"INVALID_REQUIRES_APPROVAL: {name} -> {requires!r}")
        fn = impl.split("::")[-1] if "::" in impl else None
        if fn:
            impl_to_entry[fn] = entry

    for fn in sorted(tool_functions):
        if fn not in impl_to_entry:
            kind = "mutating" if fn in mutating_functions else "read-only"
            errors.append(f"UNCLASSIFIED_TOOL: {fn} ({kind}) not in registry")
            continue
        entry = impl_to_entry[fn]
        if fn in mutating_functions:
            if entry.get("requires_approval") is not True:
                errors.append(
                    f"MUTATING_WITHOUT_APPROVAL: {fn} must have "
                    f"requires_approval = true"
                )
            if entry.get("risk_level") not in {"guarded", "dangerous"}:
                errors.append(
                    f"MUTATING_WRONG_RISK: {fn} must be guarded or dangerous, "
                    f"got {entry.get('risk_level')!r}"
                )

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(
            f"\n{len(errors)} violation(s); "
            f"{len(tool_functions)} tool function(s) introspected, "
            f"{len(mutating_functions)} mutating"
        )
        return 1

    print(
        f"OK: {len(tool_functions)} tool function(s) classified "
        f"({len(mutating_functions)} mutating, all requiring approval); "
        f"{len(tools)} registry entries valid"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
````

### ПУТЬ: scripts/check_ui_fake_state.py (107 строк, 3364 байт)

````python
"""UI fake-state gate for LocalComet (INV-UI-001).

Production UI must not generate backend state locally. State (ready, installed,
success, progress, running) must originate from backend events or invoke()
responses. This gate detects two common fake-state patterns:

  1. Math.random() anywhere in the frontend source. Fake progress/randomness
     has no legitimate place in state-bearing UI code. (LocalComet uses
     crypto.getRandomValues for identifiers, never Math.random.)

  2. A setTimeout/setInterval with a LITERAL delay >= 1000 ms placed near
     state-mutation keywords. This is the classic fake-progress shape, e.g.
     setTimeout(() => progress = 100, 2000). Legitimate polling/watchdog timers
     use named constants or variables (MANAGED_HEALTH_POLL_MS, delayMs) and are
     therefore not flagged.

Timers that merely POLL the backend (invoke inside the callback) or produce
FAILURE/timeout states are fine; this gate targets locally-fabricated success.

Exit 0 if no violations, 1 if any violation, 2 on scan error.

Injection: add `Math.random()` to a store, or
`setTimeout(() => { status = 'ready' }, 2000)` -> gate exits 1.
"""

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "desktop" / "localcomet-desktop" / "src"

STATE_KEYWORDS = (
    "store",
    "state",
    "ready",
    "status",
    "progress",
    "installed",
    "success",
    "running",
    "completed",
    "lifecycle",
)

MATH_RANDOM = re.compile(r"Math\.random\s*\(")
# setTimeout/setInterval with a literal numeric delay of >= 1000 ms.
LONG_LITERAL_TIMER = re.compile(r"set(?:Timeout|Interval)\s*\([^;]*?,\s*(\d{4,})\s*\)")


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def scan_file(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    violations = []

    for match in MATH_RANDOM.finditer(text):
        violations.append(
            f"VIOLATION [Math.random in UI source] {path}:{line_of(text, match.start())}"
        )

    for match in LONG_LITERAL_TIMER.finditer(text):
        delay = int(match.group(1))
        if delay < 1000:
            continue
        start = max(0, match.start() - 200)
        end = min(len(text), match.end() + 200)
        context = text[start:end].lower()
        if any(keyword in context for keyword in STATE_KEYWORDS):
            violations.append(
                f"VIOLATION [literal {delay}ms timer near state mutation] "
                f"{path}:{line_of(text, match.start())}"
            )

    return violations


def main() -> int:
    if not SRC_DIR.is_dir():
        print(f"FAIL: cannot find {SRC_DIR}")
        return 2

    files = [
        path
        for pattern in ("*.ts", "*.svelte", "*.js")
        for path in SRC_DIR.rglob(pattern)
        if "node_modules" not in path.parts
    ]

    all_violations = []
    for path in sorted(files):
        all_violations.extend(scan_file(path))

    if all_violations:
        for violation in all_violations:
            print(violation)
        print(f"\n{len(all_violations)} fake-state violation(s) in {len(files)} file(s)")
        return 1

    print(f"OK: no fake-state violations in {len(files)} frontend file(s) (INV-UI-001)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
````

### ПУТЬ: scripts/doctor.py (139 строк, 3946 байт)

````python
#!/usr/bin/env python3
"""LocalComet preflight check.

Run before building. Reports what is present, what is missing, and what each
missing item breaks. Exit 0 = all required items present, 1 = something is
MISSING (build would fail), 2 = internal error.

Three states per check: OK / MISSING / UNKNOWN. UNKNOWN is never collapsed into
MISSING (an unknown state is reported as such, not as knowledge).
"""

import platform
import shutil
import subprocess
import sys

CHECKS = []


def check(name, breaks):
    def decorator(fn):
        CHECKS.append((name, breaks, fn))
        return fn

    return decorator


def run(cmd, timeout=15):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, (result.stdout or result.stderr or "").strip()
    except FileNotFoundError:
        return None, "not found"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


@check("Rust toolchain (rustc/cargo)", "cargo build/test")
def rust():
    code, out = run(["rustc", "--version"])
    if code == 0:
        return True, out.split("\n")[0]
    return False, out


@check("C linker (cc or ziglang)", "Rust linking")
def linker():
    if shutil.which("cc") or shutil.which("cl") or shutil.which("link"):
        return True, "system C linker found"
    try:
        import ziglang

        return True, f"ziglang {getattr(ziglang, '__version__', 'unknown')}"
    except ImportError:
        return False, "pip install ziglang  OR install MSVC build tools"


@check("Node.js >= 18", "Svelte/npm build")
def node():
    code, out = run(["node", "--version"])
    if code == 0:
        return True, out
    return False, out


@check("npm registry (registry.npmjs.org)", "npm install")
def npm_registry():
    code, out = run(["npm", "ping"], timeout=20)
    if code == 0:
        return True, "reachable"
    return False, "UNREACHABLE (offline / blocked registry)"


@check("Python >= 3.9", "sidecar startup")
def python():
    if sys.version_info >= (3, 9):
        return True, f"python {sys.version.split()[0]}"
    return False, f"python {sys.version.split()[0]} is too old"


@check("WebView2 runtime (Windows)", "Tauri desktop window")
def webview():
    if platform.system() != "Windows":
        return None, "n/a (non-Windows)"
    try:
        import winreg

        winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"
            r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
        )
        return True, "WebView2 found"
    except OSError:
        return False, "install from https://developer.microsoft.com/microsoft-edge/webview2/"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


@check("NSIS (makensis)", "tauri build --bundle nsis")
def nsis():
    code, out = run(["makensis", "/VERSION"])
    if code == 0:
        return True, out or "found"
    return False, "install NSIS for installer bundling"


def main():
    print(f"\nLocalComet Preflight - {platform.system()} {platform.machine()}\n")
    print(f"{'Check':<38} {'Status':<9} Detail")
    print("-" * 90)

    missing = []
    for name, breaks, fn in CHECKS:
        try:
            result, detail = fn()
        except Exception as exc:  # noqa: BLE001
            result, detail = None, str(exc)
        if result is True:
            status = "OK"
        elif result is False:
            status = "MISSING"
            missing.append((name, breaks))
        else:
            status = "UNKNOWN"
        print(f"{name:<38} {status:<9} {detail}")

    print()
    if missing:
        print("BLOCKING - must fix before build:")
        for name, breaks in missing:
            print(f"  [{name}] needed for: {breaks}")
        return 1
    print("All required preflight checks passed (UNKNOWN items are non-blocking).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
````

### ПУТЬ: scripts/generate_runtime_manifest.py (88 строк, 2755 байт)

````python
#!/usr/bin/env python
"""Regenerate localcomet_runtime_manifest.json from the current source tree.

The manifest lists all Python source files categorized by role.  It must
be regenerated whenever .py files are added to or removed from the project.

Determinism check:
    python scripts/generate_runtime_manifest.py
    git diff --exit-code localcomet_runtime_manifest.json

If the diff is empty the manifest is up to date.  A non-empty diff means
the tree changed since the last committed manifest.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generate() -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {
        "entrypoints": [],
        "runtime": [],
        "lazy_runtime": [],
        "tests": [],
        "tools": [],
    }

    def rel(f: Path) -> str:
        return f.relative_to(ROOT).as_posix()

    entrypoints_set: set[str] = set()
    for name in ("app.py", "LocalComet_Control_Panel.py", "config.py", "next/app_v5.py", "GenerateCapabilityMap.py"):
        if (ROOT / name).is_file():
            categories["entrypoints"].append(name)
            entrypoints_set.add(name)

    for directory in ("core", "agents", "next"):
        dp = ROOT / directory
        if dp.is_dir():
            for f in dp.rglob("*.py"):
                r = rel(f)
                if "__pycache__" not in r and r not in entrypoints_set:
                    categories["runtime"].append(r)

    dp = ROOT / "modules"
    if dp.is_dir():
        for f in dp.rglob("*.py"):
            r = rel(f)
            if "__pycache__" not in r:
                categories["lazy_runtime"].append(r)

    dp = ROOT / "tools"
    if dp.is_dir():
        for f in dp.glob("test_*.py"):
            categories["tests"].append(rel(f))
    for f in ROOT.glob("test_*.py"):
        categories["tests"].append(rel(f))

    for directory in ("tools", "scripts"):
        dp = ROOT / directory
        if dp.is_dir():
            for f in dp.glob("*.py"):
                r = rel(f)
                if not f.name.startswith("test_") and "__pycache__" not in r:
                    categories["tools"].append(r)

    for key in categories:
        categories[key] = sorted(categories[key], key=str.casefold)

    return categories


def main() -> None:
    manifest = generate()
    out = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    target = ROOT / "localcomet_runtime_manifest.json"
    target.write_text(out, encoding="utf-8", newline="\n")
    total = sum(len(v) for v in manifest.values())
    print(f"Wrote {target.name}: {total} entries")
    for key, values in manifest.items():
        print(f"  {key}: {len(values)}")


if __name__ == "__main__":
    main()
````

### ПУТЬ: scripts/manual_model_gateway.py (48 строк, 1319 байт)

````python
import threading
import time
from modules.local_model_gateway_ru import LocalModelGateway, GatewayLimits

gateway = LocalModelGateway(limits=GatewayLimits(overall_timeout_seconds=120.0))
gateway.probe({'port': 1234})
gateway.set_binding({
    'provider_id': 'openai-compatible-local',
    'harness_id': 'minimal',
    'model_id': 'qwen/qwen3-4b-2507',
    'port': 1234,
    'confirmed': True
})

with gateway._lock:
    binding = gateway._binding
    fingerprint = binding.fingerprint

events = []
def emit(method, turn_id, sequence, payload):
    events.append((method, turn_id, sequence, payload))
    if method == 'model.output.delta':
        text = payload.get('text', '')
        print('Delta:', repr(text))
    elif method == 'model.turn.completed':
        text = payload.get('text', '')
        print('Completed:', repr(text))

result = gateway.start_turn(
    {'prompt': 'Say hello in Russian', 'binding_fingerprint': fingerprint},
    emit
)
print('Result:', result)

for _ in range(60):
    time.sleep(1)
    with gateway._lock:
        active = gateway._active
    if active and active.terminal:
        print('Turn completed')
        break
else:
    print('Timeout')

print('Total events:', len(events))
for m, t, s, p in events:
    text = p.get('text', '')
    print(f'  {m} seq={s} text={repr(text)}')
````

### ПУТЬ: scripts/refresh_evidence.py (119 строк, 4266 байт)

````python
"""Refresh LocalComet evidence with provenance headers.

Runs the project gates and records each result with a provenance header:
command, exit code, source tree digest, body SHA-256, timestamp, platform.

The tree digest binds the evidence to the exact source state. If the sources
change without re-running this script, check_evidence_provenance.py reports the
evidence as STALE (rule 1.6: stale evidence is worse than missing evidence).

Exit 0 if all gates pass, 1 otherwise.
"""

import datetime
import hashlib
import pathlib
import platform
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
EVIDENCE_DIR = REPO_ROOT / "artifacts" / "evidence"

SOURCE_GLOBS = [
    "desktop/localcomet-desktop/src-tauri/src/**/*.rs",
    "desktop/localcomet-desktop/src-tauri/Cargo.toml",
    "desktop/localcomet-desktop/src-tauri/Cargo.lock",
    "desktop/localcomet-desktop/src/**/*.ts",
    "desktop/localcomet-desktop/src/**/*.svelte",
    "desktop/contracts/*.json",
    "core/**/*.py",
    "modules/**/*.py",
    "agents/**/*.py",
    "next/**/*.py",
    "tests/**/*.py",
    "scripts/**/*.py",
    "security/invariants/*.toml",
    ".gitattributes",
    "config.py",
]

EXCLUDE_PARTS = {"__pycache__", "node_modules", ".git", "target", ".svelte-kit", "build"}


def file_sha256(path: pathlib.Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def source_files() -> list[pathlib.Path]:
    seen: set[pathlib.Path] = set()
    files: list[pathlib.Path] = []
    for pattern in SOURCE_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            if not path.is_file():
                continue
            if any(part in EXCLUDE_PARTS for part in path.parts):
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(path)
    return sorted(files, key=lambda p: p.as_posix())


def tree_digest() -> str:
    entries = []
    for path in source_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        entries.append(f"{rel}:{file_sha256(path)}")
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()


def run_and_save(name: str, cmd: list[str], digest: str) -> int:
    result = subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    body = (result.stdout or "") + (result.stderr or "")
    body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    header = (
        f"# command: {' '.join(cmd)}\n"
        f"# exit_code: {result.returncode}\n"
        f"# tree_digest: {digest}\n"
        f"# body_sha256: {body_sha}\n"
        f"# timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n"
        f"# platform: {platform.system()} {platform.machine()} python={sys.version.split()[0]}\n"
        f"# source_files: {len(source_files())}\n"
        "---\n"
    )
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE_DIR / f"{name}.txt"
    out.write_text(header + body, encoding="utf-8", newline="\n")
    status = "OK" if result.returncode == 0 else "FAIL"
    print(f"[{status}] evidence/{name}.txt exit={result.returncode} tree={digest[:16]}...")
    return result.returncode


def main() -> int:
    digest = tree_digest()
    print(f"tree_digest: {digest} ({len(source_files())} source files)")
    cargo_manifest = "desktop/localcomet-desktop/src-tauri/Cargo.toml"
    codes = [
        run_and_save("cargo_test", ["cargo", "test", "--manifest-path", cargo_manifest], digest),
        run_and_save("trust_chain", ["python", "tests/test_trust_chain_invariants.py"], digest),
        run_and_save("cmd_parity", ["python", "scripts/check_command_parity.py"], digest),
        run_and_save("tool_risk_registry", ["python", "scripts/check_tool_risk_registry.py"], digest),
    ]
    if all(code == 0 for code in codes):
        print("evidence refreshed: all gates green")
        return 0
    print("evidence refreshed: one or more gates FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
````

### ПУТЬ: scripts/smoke_test.py (170 строк, 6983 байт)

````python
#!/usr/bin/env python3
"""LocalComet smoke test — verifies the REAL desktop sidecar product path.

Drives the actual DesktopSidecarRuntime in-process via localcomet_test_harness
(the same handle_message() entry point the runner uses). Each step prints only
the observed result. Expected rejections (duplicate id, blocked filesystem
methods) are part of success.

Scope: the desktop sidecar is a model-gateway/knowledge/session manager and
performs NO filesystem tool execution. Approval and workspace confinement are
enforced in the Rust control plane and covered by `cargo test`; those steps are
reported as RUST-COVERED here, not fabricated as sidecar tool calls.

Exit: 0 = all steps gave the expected outcome
      1 = at least one step failed
      2 = environment/import unavailable
"""

import argparse
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

PASSED: list[int] = []
FAILED: list[int] = []


def ok(step: int, desc: str, detail: str = "") -> None:
    print(f"[{step:02d}] OK   {desc}" + (f" - {detail}" if detail else ""))
    PASSED.append(step)


def fail(step: int, desc: str, detail: str = "") -> None:
    print(f"[{step:02d}] FAIL {desc}" + (f" - {detail}" if detail else ""))
    FAILED.append(step)


def info(step: int, desc: str, detail: str = "") -> None:
    print(f"[{step:02d}] INFO {desc}" + (f" - {detail}" if detail else ""))


def run_smoke() -> int:
    try:
        from localcomet_test_harness import LocalCometHarness
    except ImportError as exc:
        print(f"ABORT: cannot import harness: {exc}", file=sys.stderr)
        return 2

    harness = LocalCometHarness(project_root=str(REPO_ROOT))

    # [01] Start sidecar (desktop hello handshake)
    try:
        pid, proto_version = harness.start_sidecar()
        ok(1, "sidecar start (hello handshake)", f"pid={pid} runtime={proto_version}")
    except Exception as exc:  # noqa: BLE001
        fail(1, "sidecar start", str(exc))
        return 1

    # [02] Readiness probe (active health request/response)
    try:
        status, ms = harness.readiness_probe(timeout_ms=5000)
        if status == "ok":
            ok(2, "readiness probe", f"status={status} time={ms}ms")
        else:
            fail(2, "readiness probe", f"status={status}")
    except Exception as exc:  # noqa: BLE001
        fail(2, "readiness probe", str(exc))

    # [03] runtime health
    try:
        health = harness.runtime_health()
        if health.get("status") == "ok":
            ok(3, "app.health", f"status=ok uptime_ms={health.get('uptime_ms')}")
        else:
            fail(3, "app.health", f"unexpected: {health}")
    except Exception as exc:  # noqa: BLE001
        fail(3, "app.health", str(exc))

    # [04] capabilities advertised
    # NOTE: app.health is a lifecycle endpoint handled before the capability
    # check; it is NOT part of the advertised capability set. The hello payload
    # advertises the "lifecycle" marker plus control-plane / model-gateway /
    # knowledge methods. So we assert on real advertised capabilities here.
    try:
        caps = harness.capabilities()
        needed = {"lifecycle", "model.catalog.get"}
        if needed.issubset(set(caps)):
            ok(4, "capabilities advertised", f"{len(caps)} methods incl. lifecycle+model.catalog.get")
        else:
            fail(4, "capabilities advertised", f"missing {needed - set(caps)}")
    except Exception as exc:  # noqa: BLE001
        fail(4, "capabilities advertised", str(exc))

    # [05] duplicate message id is rejected
    try:
        from modules.desktop_ipc_contract_ru import make_request

        req = make_request("smoke-dup-fixed", "app.health", {})
        first = harness.runtime.handle_message(req)
        dup = harness.runtime.handle_message(req)
        first_ok = any(r.get("payload", {}).get("status") == "ok" for r in first)
        dup_rejected = any(
            r.get("payload", {}).get("code") == "duplicate_message_id" for r in dup
        )
        if first_ok and dup_rejected:
            ok(5, "duplicate message id rejected", "duplicate_message_id")
        else:
            fail(5, "duplicate message id rejected", f"first_ok={first_ok} dup_rejected={dup_rejected}")
    except Exception as exc:  # noqa: BLE001
        fail(5, "duplicate message id rejected", str(exc))

    # [06] filesystem tool method is NOT a sidecar path (must be rejected)
    try:
        reply = harness.request("files.read", {"path": "x.txt"})
        code = reply.get("payload", {}).get("code")
        if reply.get("type") == "error" and code == "unsupported_method":
            ok(6, "files.read rejected (no sidecar fs-tool path)", "unsupported_method as expected")
        else:
            fail(6, "files.read rejected", f"unexpectedly handled: {reply}")
    except Exception as exc:  # noqa: BLE001
        fail(6, "files.read rejected", str(exc))

    # [07] model gateway catalog is reachable
    try:
        reply = harness.request("model.catalog.get", {})
        payload = reply.get("payload", {})
        if reply.get("type") == "response" and "providers" in payload:
            ok(7, "model.catalog.get", f"{len(payload.get('providers', []))} providers")
        else:
            fail(7, "model.catalog.get", f"unexpected: {reply.get('type')}")
    except Exception as exc:  # noqa: BLE001
        fail(7, "model.catalog.get", str(exc))

    # [08] shutdown produces goodbye
    try:
        replies = harness.runtime.handle_message(
            __import__("modules.desktop_ipc_contract_ru", fromlist=["make_request"]).make_request(
                "smoke-shutdown-000001", "app.shutdown", {}
            )
        )
        saw_goodbye = any(r.get("type") == "goodbye" for r in replies)
        if saw_goodbye:
            ok(8, "shutdown produces goodbye", "goodbye observed")
        else:
            fail(8, "shutdown produces goodbye", f"types={[r.get('type') for r in replies]}")
    except Exception as exc:  # noqa: BLE001
        fail(8, "shutdown produces goodbye", str(exc))

    # [09-12] Approval / workspace / filesystem enforcement: Rust-side.
    info(9, "approval token scope/replay/digest", "RUST-COVERED: cargo test approval (15 tests)")
    info(10, "workspace confinement + token invalidation", "RUST-COVERED: cargo test workspace")
    info(11, "guarded tool without approval rejected", "N/A: sidecar has no fs-tool execution path")
    info(12, "workspace escape rejected", "RUST-COVERED + modules/workspace_policy.py self-test")

    print()
    print(f"Results: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print(f"Failed steps: {FAILED}")
        return 1
    print("SMOKE PASSED: real sidecar product path behaves as expected.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["cli", "full"], default="full")
    parser.parse_args()
    sys.exit(run_smoke())
````

### ПУТЬ: security/invariants/invariants.toml (208 строк, 8168 байт)

````toml
# LocalComet Security Invariants Registry
# Machine-readable invariant definitions with test bindings.

schema_version = 1

[[invariants]]
id = "INV-PROCESS-001"
title = "Desktop owns entire sidecar process tree"
statement = "The Tauri desktop process owns the sidecar and all descendants via Windows Job Object with KILL_ON_JOB_CLOSE and ACTIVE_PROCESS_LIMIT=1. No orphan processes survive desktop termination."
severity = "critical"
owner = "windows_job.rs, supervisor.rs"
implementation = [
    "desktop/localcomet-desktop/src-tauri/src/windows_job.rs",
    "desktop/localcomet-desktop/src-tauri/src/supervisor.rs",
]
test_ids = [
    "source_sets_active_process_limit_to_one",
    "command_line_quotes_python_runner_and_flags",
    "environment_block_is_double_null_terminated",
]
status = "active"

[[invariants]]
id = "INV-READINESS-001"
title = "Ready requires active correlated health response"
statement = "Sidecar readiness is confirmed only after an active health probe (desk-health-{seq}) receives a correlated response with payload.status=ok. Passive hello events alone are insufficient."
severity = "critical"
owner = "supervisor.rs"
implementation = [
    "desktop/localcomet-desktop/src-tauri/src/supervisor.rs",
]
test_ids = [
    "lifecycle_frame_observation_requires_exact_health_response_shape",
    "real_python_sidecar_can_start_when_test_environment_is_present",
    "failed_readiness_stops_the_contained_sidecar",
]
status = "active"

[[invariants]]
id = "INV-IPC-001"
title = "IPC frames are bounded and length-prefixed"
statement = "All IPC frames use 4-byte big-endian length prefix. Maximum frame size is 4MiB. Zero-length and oversized frames are rejected without allocation."
severity = "high"
owner = "ipc.rs"
implementation = [
    "desktop/localcomet-desktop/src-tauri/src/ipc.rs",
]
test_ids = [
    "frames_are_big_endian_length_prefixed_json",
    "reader_rejects_zero_length_frame",
]
status = "active"

[[invariants]]
id = "INV-IPC-002"
title = "Pipe writes are bounded with timeout"
statement = "Writing to sidecar stdin uses bounded retry with timeout. A non-reading sidecar cannot block the desktop indefinitely. Write failure terminates the sidecar and fails pending requests."
severity = "high"
owner = "windows_job.rs, supervisor.rs"
implementation = [
    "desktop/localcomet-desktop/src-tauri/src/windows_job.rs",
    "desktop/localcomet-desktop/src-tauri/src/supervisor.rs",
]
test_ids = [
    "bounded_writer_preserves_complete_frame_order_across_partial_writes",
    "bounded_writer_times_out_when_pipe_never_accepts_data",
    "bounded_writer_propagates_sidecar_failure_without_retrying",
    "nonreading_sidecar_pipe_write_is_bounded_and_releases_supervisor",
]
status = "active"

[[invariants]]
id = "INV-CATALOG-001"
title = "Artifact catalog is embedded, hash-pinned, and canonical"
statement = "The approved artifact catalog is compiled into the binary with a pinned SHA-256. It must be canonical JSON (LF, no BOM, no trailing whitespace, single final LF, sorted keys). Any deviation is rejected at startup."
severity = "critical"
owner = "artifact_trust.rs"
implementation = [
    "desktop/localcomet-desktop/src-tauri/src/artifact_trust.rs",
]
test_ids = []
status = "active"

[[invariants]]
id = "INV-CATALOG-002"
title = "LLM, filename, and app-data are not catalog approval authority"
statement = "Model/runtime approval requires embedded catalog record with SHA-256. No LLM output, filename pattern, or database record can substitute for catalog verification."
severity = "critical"
owner = "artifact_trust.rs"
implementation = [
    "desktop/localcomet-desktop/src-tauri/src/artifact_trust.rs",
    "security/invariants/non_authorities.toml",
]
test_ids = []
status = "active"

[[invariants]]
id = "INV-MODEL-001"
title = "Model cannot be installed or launched without verified digest"
statement = "Model validation requires: correct size, GGUF magic bytes, SHA-256 match against catalog. Launch requires re-validation after opening file handles (TOCTOU mitigation)."
severity = "critical"
owner = "artifact_trust.rs"
implementation = [
    "desktop/localcomet-desktop/src-tauri/src/artifact_trust.rs",
]
test_ids = []
status = "active"

[[invariants]]
id = "INV-PROCESS-002"
title = "Sidecar environment is sanitized"
statement = "Sidecar runs with -I (isolated) and -B (no bytecode) flags. Environment contains only lifecycle-safe variables. No TOKEN, SECRET, or user-site packages are accessible."
severity = "high"
owner = "supervisor.rs"
implementation = [
    "desktop/localcomet-desktop/src-tauri/src/supervisor.rs",
]
test_ids = [
    "environment_keeps_only_lifecycle_safe_python_values",
    "debug_launch_spec_uses_fixed_python_runner_arguments",
]
status = "active"

[[invariants]]
id = "INV-UI-001"
title = "Production UI does not generate false backend state"
statement = "All UI state transitions (ready, running, installed, success) must originate from backend events. No Math.random(), no timer-based progress, no optimistic success without backend confirmation."
severity = "high"
owner = "Svelte frontend"
implementation = [
    "desktop/localcomet-desktop/src/",
    "scripts/check_ui_fake_state.py",
]
test_ids = []
verification_method = "scripts/check_ui_fake_state.py [прогон]"
verified_at = "2026-07-25"
status = "active"

[[invariants]]
id = "INV-EVIDENCE-001"
title = "Evidence is bound to all execution inputs"
statement = "Test evidence must include source tree digest, command argv, exit code, tool versions, and timestamp. Evidence without source binding is stale and must not be treated as proof."
severity = "medium"
owner = "scripts/"
implementation = [
    "scripts/refresh_evidence.py",
    "scripts/check_evidence_provenance.py",
]
test_ids = [
    "check_evidence_provenance_detects_stale",
]
verification_method = "scripts/check_evidence_provenance.py [прогон] + injection (modify covered source -> STALE, exit 1)"
verified_at = "2026-07-25"
status = "active"

[[invariants]]
id = "INV-APPROVAL-001"
title = "Guarded tool cannot execute without atomic Rust authorization"
statement = "Any guarded or dangerous tool call must pass through execute_approved() which atomically validates scope (tool, input digest, workspace, session, expiry), consumes the one-time token, and creates an execution grant. No bypass path exists."
severity = "critical"
owner = "approval.rs + approval_commands.rs"
implementation = [
    "desktop/localcomet-desktop/src-tauri/src/approval.rs",
    "desktop/localcomet-desktop/src-tauri/src/approval_commands.rs",
]
test_ids = [
    "execute_approved_succeeds_with_matching_scope",
    "replay_is_rejected",
    "wrong_tool_is_rejected",
    "wrong_input_digest_is_rejected",
    "wrong_workspace_is_rejected",
    "wrong_session_is_rejected",
    "expired_token_is_rejected",
]
verification_method = "cargo test approval [прогон]"
verified_at = "2026-07-25"
status = "active"

[[invariants]]
id = "INV-APPROVAL-002"
title = "Approval token is one-time, scoped, and CSPRNG-generated"
statement = "Approval tokens use getrandom/OsRng with minimum 256 bits. Tokens are bound to tool, canonical input digest, workspace, session, and expiry. Each token can be consumed exactly once. Comparison uses constant-time equality."
severity = "critical"
owner = "approval.rs"
implementation = [
    "desktop/localcomet-desktop/src-tauri/src/approval.rs",
]
test_ids = [
    "issued_tokens_are_unique_and_256_bits",
    "two_registries_issue_different_first_tokens",
    "replay_is_rejected",
    "ttl_sweep_frees_expired_slots_before_capacity_check",
    "execution_grant_carries_short_lived_expiry",
    "invalid_prefix_is_rejected",
]
verification_method = "cargo test approval [прогон]"
verified_at = "2026-07-25"
status = "active"

[[invariants]]
id = "INV-WORKSPACE-001"
title = "Sidecar uses confirmed current workspace"
statement = "Workspace changes require IPC round-trip (workspace.set.request/response). Old approval tokens are invalidated on workspace change. Filesystem operations are blocked during transition."
severity = "high"
owner = "workspace.rs (planned)"
implementation = []
test_ids = []
status = "planned"
````

