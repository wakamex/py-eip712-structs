"""EIP712 data structure management for python."""

# required before imports to avoid circular dependency
# pylint: disable=wrong-import-position
# pylint: disable=invalid-name
default_domain = None

from eip712_structs.domain_separator import make_domain
from eip712_structs.struct import EIP712Struct
from eip712_structs.types import Address, Array, Boolean, Bytes, Int, String, Uint
