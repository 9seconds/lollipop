from zephyr.errors import ValidationError, ValidationErrorBuilder, merge_errors
from zephyr.utils import is_list, is_dict
from zephyr.compat import string_types, int_types, iteritems


MISSING = object()

MISSING_ERROR_MESSAGE = 'Error message "{key}" in class {class_name} does not exist'


class Type(object):
    default_error_messages = {
        'invalid_type': 'Value should be {expected}',
        'required': 'Value is required',
    }

    def __init__(self, validate=None, error_messages=None):
        super(Type, self).__init__()
        if validate is None:
            validate = []
        elif callable(validate):
            validate = [validate]

        self._validators = validate
        self._error_messages = dict(self.default_error_messages,
                                    **(error_messages or {}))

    def validate(self, data):
        try:
            self.load(data)
            return {}
        except ValidationError as ve:
            return ve.messages

    def load(self, data):
        errors_builder = ValidationErrorBuilder()
        for validator in self._validators:
            try:
                validator(data)
            except ValidationError as ve:
                errors_builder.add_errors(ve.messages)
        errors_builder.raise_errors()
        return data

    def dump(self, value):
        return value

    def _fail(self, key, **kwargs):
        if key not in self._error_messages:
            msg = MISSING_ERROR_MESSAGE.format(
                class_name=self.__class__.__name__,
                key=key
            )
            raise ValueError(msg)

        msg = self._error_messages[key]
        if isinstance(msg, str):
            msg = msg.format(**kwargs)

        raise ValidationError(msg)



class Any(Type):
    pass


class Integer(Type):
    def load(self, data):
        if data is MISSING or data is None:
            self._fail('required')

        if not isinstance(data, int_types):
            self._fail('invalid_type', expected='integer')
        return super(Integer, self).load(data)

    def dump(self, value):
        if value is MISSING or value is None:
            self._fail('required')

        if not isinstance(value, int_types):
            self._fail('invalid_type', expected='integer')
        return super(Integer, self).dump(value)


class String(Type):
    def load(self, data):
        if data is MISSING or data is None:
            self._fail('required')

        if not isinstance(data, string_types):
            self._fail('invalid_type', expected='string')
        return super(String, self).load(data)

    def dump(self, value):
        if value is MISSING or value is None:
            self._fail('required')

        if not isinstance(value, string_types):
            self._fail('invalid_type', expected='string')
        return super(String, self).dump(str(value))


class Boolean(Type):
    def load(self, data):
        if data is MISSING or data is None:
            self._fail('required')

        if not isinstance(data, bool):
            self._fail('invalid_type', expected='boolean')
        return super(Boolean, self).load(data)

    def dump(self, value):
        if value is MISSING or value is None:
            self._fail('required')

        if not isinstance(value, bool):
            self._fail('invalid_type', expected='boolean')
        return super(Boolean, self).dump(bool(value))


class List(Type):
    def __init__(self, item_type, **kwargs):
        super(List, self).__init__(**kwargs)
        self.item_type = item_type

    def load(self, data):
        if data is MISSING or data is None:
            self._fail('required')

        # TODO: Make more intelligent check for collections
        if not is_list(data):
            self._fail('invalid_type', expected='list')

        errors_builder = ValidationErrorBuilder()
        items = []
        for idx, item in enumerate(data):
            try:
                items.append(self.item_type.load(item))
            except ValidationError as ve:
                errors_builder.add_errors({idx: ve.messages})
        errors_builder.raise_errors()

        return super(List, self).load(items)

    def dump(self, value):
        if value is MISSING or value is None:
            self._fail('required')

        if not is_list(value):
            self._fail('invalid_type', expected='list')

        errors_builder = ValidationErrorBuilder()
        items = []
        for idx, item in enumerate(value):
            try:
                items.append(self.item_type.dump(item))
            except ValidationError as ve:
                errors_builder.add_errors({idx: ve.messages})
        errors_builder.raise_errors()

        return super(List, self).dump(items)


class Tuple(Type):
    default_error_messages = dict(Type.default_error_messages, **{
        'invalid_length': 'Value length should be {expected_length}',
    })

    def __init__(self, item_types, **kwargs):
        super(Tuple, self).__init__(**kwargs)
        self.item_types = item_types

    def load(self, data):
        if data is MISSING or data is None:
            self._fail('required')

        if not is_list(data):
            self._fail('invalid_type', expected='list')

        if len(data) != len(self.item_types):
            self._fail('invalid_length', expected_length=len(self.item_types))

        errors_builder = ValidationErrorBuilder()
        result = []
        for idx, (item_type, item) in enumerate(zip(self.item_types, data)):
            try:
                result.add(item_type.load(item))
            except ValidationError as ve:
                errors_builder.add_errors({idx: ve.messages})
        errors_builder.raise_errors()

        return super(Tuple, self).load(result)

    def dump(self, value):
        if value is MISSING or value is None:
            self._fail('required')

        if not is_list(data):
            self._fail('invalid_type', expected='list')

        if len(value) != len(self.item_types):
            self._fail('invalid_length', expected_length=len(self.item_types))

        errors_builder = ValidationErrorBuilder()
        result = []
        for idx, (item_type, item) in enumerate(zip(self.item_types, value)):
            try:
                result.add(item_type.dump(item))
            except ValidationError as ve:
                errors_builder.add_errors({idx: ve.messages})
        errors_builder.raise_errors()

        return super(Tuple, self).dump(result)


class DictWithDefault(object):
    def __init__(self, values={}, default=None):
        super(DictWithDefault, self).__init__()
        self.values = values
        self.default = default

    def __len__(self):
        return len(self.values)

    def __getitem__(self, key):
        if key in self.values:
            return self.values[key]
        return self.default

    def __setitem__(self, key, value):
        self.values[key] = value

    def __delitem__(self, key):
        del self.values[key]

    def get(self, key, default=None):
        return self[key]


class Dict(Type):
    def __init__(self, value_type=Any(), **kwargs):
        super(Dict, self).__init__(**kwargs)
        if isinstance(value_type, Type):
            value_type = DictWithDefault(default=value_type)
        self.value_types = value_type

    def load(self, data):
        if data is MISSING or data is None:
            self._fail('required')

        if not is_dict(data):
            self._fail('invalid_type', expected='dict')

        errors_builder = ValidationErrorBuilder()
        result = {}
        for k, v in iteritems(data):
            value_type = self.value_types.get(k)
            if value_type is None:
                continue
            try:
                result[k] = value_type.load(v)
            except ValidationError as ve:
                errors_builder.add_error(k, ve.messages)
        errors_builder.raise_errors()

        return super(Dict, self).load(result)

    def dump(self, value):
        if value is MISSING or value is None:
            self._fail('required')

        if not is_dict(value):
            self._fail('invalid_type', expected='dict')

        errors_builder = ValidationErrorBuilder()
        result = {}
        for k, v in iteritems(value):
            value_type = self.value_types.get(k)
            if value_type is None:
                continue
            try:
                result[k] = value_type.dump(v)
            except ValidationError as ve:
                errors_builder.add_error(k, ve.messages)
        errors_builder.raise_errors()

        return super(Dict, self).dump(result)


class Field(object):
    def __init__(self, field_type):
        super(Field, self).__init__()
        self.field_type = field_type

    def _get_value(self, name, obj):
        raise NotImplemented()

    def load(self, name, data):
        return MISSING

    def dump(self, name, obj):
        value = self._get_value(name, obj)
        return self.field_type.dump(value)


class ConstantField(Field):
    def __init__(self, field_type, value):
        super(ConstantField, self).__init__(field_type)
        self.value = value

    def _get_value(self, name, obj):
        return self.value


class AttributeField(Field):
    def __init__(self, field_type, attribute=None):
        super(AttributeField, self).__init__(field_type)
        self.attribute = attribute

    def _get_value(self, name, obj):
        return getattr(obj, self.attribute or name, MISSING)

    def load(self, name, data):
        value = data.get(name, MISSING)
        return self.field_type.load(value)


class MethodField(Field):
    def __init__(self, field_type, method=None):
        super(MethodField, self).__init__(field_type)
        self.method = method

    def _get_value(self, name, obj):
        if self.method:
            name = self.method
        if not hasattr(obj, name):
            raise ValueError('Object does not have method %s' % name)
        if not callable(getattr(obj, name)):
            raise ValueError('Value %s is not callable' % name)
        return getattr(obj, name)()


class FunctionField(Field):
    def __init__(self, field_type, function):
        super(FunctionField, self).__init__(field_type)
        self.function = function

    def _get_value(self, name, obj):
        return self.function(name, obj)


class Object(Type):
    default_error_messages = dict(Type.default_error_messages, **{
        'unknown': 'Unknown field',
    })

    def __init__(self, fields, constructor=dict,
                 default_field_type=AttributeField,
                 allow_extra_fields=True,
                 **kwargs):
        super(Object, self).__init__(**kwargs)
        self.fields = dict([
            (name, field if isinstance(field, Field) else default_field_type(field))
            for name, field in iteritems(fields)
        ])
        self.constructor = constructor
        self.allow_extra_fields = allow_extra_fields

    def load(self, data):
        if data is MISSING or data is None:
            self._fail('required')

        if not is_dict(data):
            self._fail('invalid_type', expected='dict')

        errors_builder = ValidationErrorBuilder()
        result = {}
        for name, field in iteritems(self.fields):
            try:
                loaded = field.load(name, data)
                if loaded != MISSING:
                    result[name] = loaded
            except ValidationError as ve:
                errors_builder.add_error(name, ve.messages)

        if not self.allow_extra_fields:
            for name in data:
                if name not in self.fields:
                    errors_builder.add_error(name, self._error_messages['unknown'])

        errors_builder.raise_errors()

        return self.constructor(**super(Object, self).load(result))

    def dump(self, obj):
        if obj is MISSING or obj is None:
            self._fail('required')

        errors_builder = ValidationErrorBuilder()
        result = {}
        for name, field in iteritems(self.fields):
            try:
                dumped = field.dump(name, obj)
                if dumped != MISSING:
                    result[name] = dumped
            except ValidationError as ve:
                errors_builder.add_error(k, ve.messages)
        errors_builder.raise_errors()

        return super(Object, self).dump(result)
