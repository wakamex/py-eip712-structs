"""EIP-712 Structs."""

import functools
import json
import operator
import re
from collections import defaultdict
from typing import List, NamedTuple, Tuple

from eth_utils.crypto import keccak

import eip712_structs
from eip712_structs.types import Array, BytesJSONEncoder, EIP712Type, from_solidity_type


class EIP712Struct(EIP712Type):
    """Represent an EIP712 struct. Subclass it to use it.

    Examples:
        from eip712_structs import EIP712Struct, String

        class MyStruct(EIP712Struct):
            some_param = String()

        struct_instance = MyStruct(some_param='some_value')
    """

    def __init__(self, **kwargs):
        """Initialize the struct."""
        super().__init__(type_name=self.type_name, none_val=None)
        self.values = {}
        for name, typ in self.get_members():
            value = kwargs.get(name)
            if isinstance(value, dict):
                # check if it's callable
                if callable(typ):
                    value = typ(**value)
                else:
                    raise TypeError(f"Cannot create {typ.__class__.__name__} from {value}")
            self.values[name] = value

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Initialize the subclass."""
        super().__init_subclass__(**kwargs)
        cls.type_name = cls.__name__

    def _encode_value(self, value=None):
        """Return the struct's encoded value.

        A struct's encoded value is a concatenation of the bytes32 representation of each member of the struct.

        Args:
            value (Any): This parameter is not used for structs.
        """
        encoded_values = []
        for name, typ in self.get_members():
            if isinstance(typ, type) and issubclass(typ, EIP712Struct):
                # Nested structs are recursively hashed, with the resulting 32-byte hash appended to the list of values
                sub_struct = self.get_data_value(name)
                assert sub_struct is not None, f"Value for {name} not set"
                encoded_values.append(sub_struct.hash_struct())
            else:
                # Regular types are encoded as normal
                encoded_values.append(typ.encode_value(self.values[name]))
        return b"".join(encoded_values)

    def get_data_value(self, name):
        """Get the value of the given struct parameter."""
        return self.values.get(name)

    def set_data_value(self, name, value):
        """Set the value of the given struct parameter."""
        if name in self.values:
            self.values[name] = value

    def data_dict(self):
        """Provide the entire data dictionary representing the struct.

        Nested structs instances are also converted to dict form.
        """
        return {k: v.data_dict() if isinstance(v, EIP712Struct) else v for k, v in self.values.items()}

    @classmethod
    def _encode_type(cls, resolve_references: bool) -> str:
        member_sigs = [f"{typ.type_name} {name}" for name, typ in cls.get_members()]
        struct_sig = f'{cls.type_name}({",".join(member_sigs)})'

        if resolve_references:
            reference_structs = set()
            cls._gather_reference_structs(reference_structs)
            sorted_structs = sorted(
                [s for s in reference_structs if s != cls],
                key=lambda s: s.type_name,
            )
            for struct in sorted_structs:
                struct_sig += struct._encode_type(resolve_references=False)  # pylint: disable=protected-access
        return struct_sig

    @classmethod
    def _gather_reference_structs(cls, struct_set):
        """Find reference structs defined in this struct type, and inserts them into the given set."""
        structs = [m[1] for m in cls.get_members() if isinstance(m[1], type) and issubclass(m[1], EIP712Struct)]
        for struct in structs:
            if struct not in struct_set:
                struct_set.add(struct)
                struct._gather_reference_structs(struct_set)  # pylint: disable=protected-access

    @classmethod
    def encode_type(cls):
        """Get the encoded type signature of the struct.

        Nested structs are also encoded, and appended in alphabetical order.
        """
        return cls._encode_type(resolve_references=True)

    @classmethod
    def type_hash(cls) -> bytes:
        """Get the keccak hash of the struct's encoded type."""
        return keccak(text=cls.encode_type())

    def hash_struct(self) -> bytes:
        """Return the hash of the struct.

        hash_struct => keccak(type_hash || encode_data)
        """
        return keccak(b"".join([self.type_hash(), self.encode_value()]))

    @classmethod
    def get_members(cls) -> List[Tuple[str, EIP712Type | type[EIP712Type]]]:
        """Return a list of tuples of supported parameters.

        Each tuple is (<parameter_name>, <parameter_type>).
        """
        return [
            (name, attr)
            for name, attr in cls.__dict__.items()
            if isinstance(attr, EIP712Type) or isinstance(attr, type) and issubclass(attr, EIP712Type)
        ]

    @staticmethod
    def _assert_domain(domain: "EIP712Struct | None") -> "EIP712Struct":
        if result := domain or eip712_structs.default_domain:
            return result
        raise ValueError("Domain must be provided, or eip712_structs.default_domain must be set.")

    def to_message(self, domain: "EIP712Struct | None" = eip712_structs.default_domain) -> dict:
        """Convert a struct into a dictionary suitable for messaging.

        Dictionary is of the form:
            {
                'primaryType': Name of the primary type,
                'types': Definition of each included struct type (including the domain type)
                'domain': Values for the domain struct,
                'message': Values for the message struct,
            }

        Args:
            domain (EIP712Struct | None, optional): The domain struct to include in the message.
                Use `eip712_structs.default_domain` if None.

        Returns:
            dict: This struct + the domain in dict form, structured as specified for EIP712 messages.
        """
        domain = self._assert_domain(domain)
        structs = {domain, self}
        self._gather_reference_structs(structs)

        # Build type dictionary
        types = {}
        for struct in structs:
            members_json = [
                {
                    "name": m[0],
                    "type": m[1].type_name,
                }
                for m in struct.get_members()
            ]
            types[struct.type_name] = members_json

        return {
            "primaryType": self.type_name,
            "types": types,
            "domain": domain.data_dict(),
            "message": self.data_dict(),
        }

    def to_message_json(self, domain: "EIP712Struct | None" = None) -> str:
        """Convert a struct into a JSON string suitable for messaging.

        Returns:
            str: This struct + the domain in JSON form, structured as specified for EIP712 messages.
        """
        message = self.to_message(domain)
        return json.dumps(message, cls=BytesJSONEncoder)

    def signable_bytes(self, domain: "EIP712Struct | None" = None) -> bytes:
        r"""Construct a byte object suitable for signing based on the EIP712 spec.

        This method prefixes the byte string with `b'\x19\x01'` and appends hashes of the
        domain and structure, which are used to produce the final signable byte object.

        Args:
            domain (EIP712Struct | None, optional): The domain to include in the hash bytes.
                Use `eip712_structs.default_domain` if None.

        Returns:
            bytes: A 32-byte object containing the encoded data suitable for signing.
        """
        domain = self._assert_domain(domain)
        return b"\x19\x01" + domain.hash_struct() + self.hash_struct()

    @classmethod
    def from_message(cls, message_dict: dict) -> "StructTuple":
        """Convert a message dictionary into two EIP712Struct objects - one for domain, another for the message struct.

        Returned as a StructTuple, which has the attributes ``message`` and ``domain``.

        Examples:
            my_msg = { .. }
            deserialized = EIP712Struct.from_message(my_msg)
            msg_struct = deserialized.message
            domain_struct = deserialized.domain

        Args:
            message_dict (dict): The dictionary, such as what is produced by EIP712Struct.to_message.

        Returns:
            StructTuple: A StructTuple object, containing the message and domain structs.
        """
        structs = {}
        unfulfilled_struct_params = defaultdict(list)

        for type_name in message_dict["types"]:
            # Dynamically construct struct class from dict representation
            struct_from_json = type(type_name, (EIP712Struct,), {})
            for member in message_dict["types"][type_name]:
                # Either a basic solidity type is set, or None if referring to a reference struct (we'll fill it later)
                setattr(struct_from_json, member["name"], from_solidity_type(member["type"]))
                if getattr(struct_from_json, member["name"]) is None:
                    # Track the refs we'll need to set later.
                    unfulfilled_struct_params[type_name].append((member["name"], member["type"]))
            structs[type_name] = struct_from_json

        regex_pattern = r"([a-zA-Z0-9_]+)(\[(\d+)?\])?"

        # Now that custom structs have been parsed, pass through again to set the references
        for struct_name, unfulfilled_member_names in unfulfilled_struct_params.items():
            for name, type_name in unfulfilled_member_names:
                match = re.match(regex_pattern, type_name)
                assert match is not None, f'"{type_name}" is not a valid type name.'
                ref_struct = structs[match[1]]
                if match[2]:
                    # The type is an array of the struct
                    arr_len = match[3] or 0
                    setattr(structs[struct_name], name, Array(ref_struct, int(arr_len)))
                else:
                    setattr(structs[struct_name], name, ref_struct)

        return StructTuple(
            message=structs[message_dict["primaryType"]](**message_dict["message"]),
            domain=structs["EIP712Domain"](**message_dict["domain"]),
        )

    @classmethod
    def _assert_key_is_member(cls, key):
        member_names = {tup[0] for tup in cls.get_members()}
        if key not in member_names:
            raise KeyError(f'"{key}" is not defined for this struct.')

    @classmethod
    def _assert_property_type(cls, key, value):
        """Eagerly check for a correct member type."""
        members = dict(cls.get_members())
        typ = members[key]

        if isinstance(typ, type) and issubclass(typ, EIP712Struct):
            # We expect an EIP712Struct instance. Assert that's true, and check the struct signature too.
            if not isinstance(value, EIP712Struct) or value._encode_type(False) != typ._encode_type(False):  # pylint: disable=protected-access
                raise ValueError(f"Given value is of type {type(value)}, but we expected {typ}")
        else:
            # Since it isn't a nested struct, its an EIP712Type
            try:
                typ.encode_value(value)
            except Exception as exc:
                raise ValueError(
                    f"The python type {type(value)} does not appear " f"to be supported for data type {typ}."
                ) from exc

    def __getitem__(self, key):
        """Return the underlying value dictionary."""
        self._assert_key_is_member(key)
        return self.values.__getitem__(key)

    def __setitem__(self, key, value):
        """Set the underlying value dictionary."""
        self._assert_key_is_member(key)
        self._assert_property_type(key, value)

        return self.values.__setitem__(key, value)

    def __delitem__(self, _):
        """Disallow deleting an entry."""
        raise TypeError("Deleting entries from an EIP712Struct is not allowed.")

    def __eq__(self, other):
        """Equality is determined by type equality and value equality."""
        if not other:
            # Null check
            return False
        if self is other:
            # Check identity
            return True
        if not isinstance(other, EIP712Struct):
            # Check class
            return False
        # Our structs are considered equal if their type signature and encoded value signature match.
        # E.g., like computing signable bytes but without a domain separator
        return self.encode_type() == other.encode_type() and self.encode_value() == other.encode_value()

    def __hash__(self):
        """Hash is determined by the type name and value hash."""
        value_hashes = [hash(k) ^ hash(v) for k, v in self.values.items()]
        return functools.reduce(operator.xor, value_hashes, hash(self.type_name))


class StructTuple(NamedTuple):
    """A tuple containing an EIP712Struct and an EIP712Struct."""

    message: EIP712Struct
    domain: EIP712Struct
