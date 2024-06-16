# EIP-712 Structs  [![Build Status](https://travis-ci.org/ConsenSys/py-eip712-structs.svg?branch=master)](https://travis-ci.org/ConsenSys/py-eip712-structs) [![Coverage Status](https://coveralls.io/repos/github/ConsenSys/py-eip712-structs/badge.svg?branch=master)](https://coveralls.io/github/ConsenSys/py-eip712-structs?branch=master)

A python interface for simple EIP-712 struct construction.

In this module, a "struct" is structured data as defined in the standard.
It is not the same as the Python Standard Library's struct (e.g., `import struct`).

Read the proposal:<br/>
https://github.com/ethereum/EIPs/blob/master/EIPS/eip-712.md

#### Supported Python Versions
- 3.10 and up, tested up to 3.12

## Usage

### `class EIP712Struct`
#### Important methods
- `.to_message(domain: EIP712Struct)` - Convert the struct (and given domain struct) into the standard EIP-712 message structure.
- `.signable_bytes(domain: EIP712Struct)` - Get the standard EIP-712 bytes hash, suitable for signing.
- `.from_message(message_dict: dict)` **(Class method)** - Given a standard EIP-712 message dictionary (such as produced from `.to_message`), returns a NamedTuple containing the `message` and `domain` EIP712Structs.

#### Other stuff
- `.encode_value()` - Returns a `bytes` object containing the ordered concatenation of each members bytes32 representation.
- `.encode_type()` **(Class method)** - Gets the "signature" of the struct class. Includes nested structs too!
- `.type_hash()` **(Class method)** - The keccak256 hash of the result of `.encode_type()`.
- `.hash_struct()` - Gets the keccak256 hash of the concatenation of `.type_hash()` and `.encode_value()`
- `.get_data_value(member_name: str)` - Get the value of the given struct member
- `.set_data_value(member_name: str, value: Any)` - Set the value of the given struct member
- `.data_dict()` - Returns a dictionary with all data in this struct. Includes nested struct data, if exists.
- `.get_members()` **(Class method)** - Returns a dictionary mapping each data member's name to it's type.

Examples/Details below.

#### Quickstart
Say we want to represent the following struct, convert it to a message and sign it:
```text
struct MyStruct {
    string some_string;
    uint256 some_number;
}
```

With this module, that would look like:
```python
# Make a unique domain
from eip712_structs import make_domain
domain = make_domain(name='Some name', version='1.0.0')  # Make a Domain Separator

# Define your struct type
from eip712_structs import EIP712Struct, String, Uint
class MyStruct(EIP712Struct):
    some_string = String()
    some_number = Uint(256)

# Create an instance with some data
mine = MyStruct(some_string='hello world', some_number=1234)

# Values can be get/set dictionary-style:
mine['some_number'] = 4567
assert mine['some_string'] == 'hello world'
assert mine['some_number'] == 4567

# Into a message dict - domain required
my_msg = mine.to_message(domain)

# Into message JSON - domain required.
# This method converts bytes types for you, which the default JSON encoder won't handle.
my_msg_json = mine.to_message_json(domain)

# Into signable bytes - domain required
my_bytes = mine.signable_bytes(domain)
```

See [Member Types](#member-types) for more information on supported types.

#### Dynamic construction
Attributes may be added dynamically as well. This may be necessary if you
want to use a reserved keyword like `from`.

```python
from eip712_structs import EIP712Struct, Address
class Message(EIP712Struct):
    pass

Message.to = Address()
setattr(Message, 'from', Address())

# At this point, Message is equivalent to `struct Message { address to; address from; }`

```

#### The domain separator
EIP-712 specifies a domain struct, to differentiate between identical structs that may be unrelated.
A helper method exists for this purpose.
All values to the `make_domain()`
function are optional - but at least one must be defined. If omitted, the resulting
domain struct's definition leaves out the parameter entirely.

The full signature: <br/>
`make_domain(name: string, version: string, chainId: uint256, verifyingContract: address, salt: bytes32)`

##### Setting a default domain
Constantly providing the same domain can be cumbersome. You can optionally set a default, and then forget it.
It is automatically used by `.to_message()` and `.signable_bytes()`

```python
import eip712_structs

foo = SomeStruct()

my_domain = eip712_structs.make_domain(name='hello world')
eip712_structs.default_domain = my_domain

assert foo.to_message() == foo.to_message(my_domain)
assert foo.signable_bytes() == foo.signable_bytes(my_domain)
```

## Member Types

### Basic types
EIP712's basic types map directly to solidity types.

```python
from eip712_structs import Address, Boolean, Bytes, Int, String, Uint

Address()  # Solidity's 'address'
Boolean()  # 'bool'
Bytes()    # 'bytes'
Bytes(N)   # 'bytesN' - N must be an int from 1 through 32
Int(N)     # 'intN' - N must be a multiple of 8, from 8 to 256
String()   # 'string'
Uint(N)    # 'uintN' - N must be a multiple of 8, from 8 to 256
```

Use like:
```python
from eip712_structs import EIP712Struct, Address, Bytes

class Foo(EIP712Struct):
    member_name_0 = Address()
    member_name_1 = Bytes(5)
    # ...etc
```

### Struct references
In addition to holding basic types, EIP712 structs may also hold other structs!
Usage is almost the same - the difference is you don't "instantiate" the class.

Example:
```python
from eip712_structs import EIP712Struct, String

class Dog(EIP712Struct):
    name = String()
    breed = String()

class Person(EIP712Struct):
    name = String()
    dog = Dog  # Take note - no parentheses!

# Dog "stands alone"
Dog.encode_type()     # Dog(string name,string breed)

# But Person knows how to include Dog
Person.encode_type()  # Person(string name,Dog dog)Dog(string name,string breed)
```

Instantiating the structs with nested values may be done a couple different ways:

```python
# Method one: set it to a struct
dog = Dog(name='Mochi', breed='Corgi')
person = Person(name='E.M.', dog=dog)

# Method two: set it to a dict - the underlying struct is built for you
person = Person(
    name='E.M.',
    dog={
        'name': 'Mochi',
        'breed': 'Corgi',
    }
)
```

### Arrays
Arrays are also supported for the standard.

```python
array_member = Array(<item_type>[, <optional_length>])
```

- `<item_type>` - The basic type or struct that will live in the array
- `<optional_length>` - If given, the array is set to that length.

For example:
```python
dynamic_array = Array(String())      # String[] dynamic_array
static_array  = Array(String(), 10)  # String[10] static_array
struct_array = Array(MyStruct, 10)   # MyStruct[10] - again, don't instantiate structs like the basic types
```

## Development
Contributions always welcome.

Install test dependencies:
- `uv pip install -e ".[test]"`

Run tests:
- `pytest`
- Some tests expect an active local anvil chain on http://localhost:11111. Docker will compile the contracts and start the chain for you.
- Docker is optional, but useful to test the whole suite. If no chain is detected, chain tests are skipped.
- Usage:
    - `docker-compose up -d` (Starts containers in the background)
    - Note: Contracts are compiled when you run `up`, but won't be deployed until the test is run.
    - Cleanup containers when you're done: `docker-compose down`

Deploying a new version:
- Bump the version number in `pyproject.toml`, commit it into master.
- Make a release tag on the master branch in Github. Travis should handle the rest.

### Changes in 1.2
- Switch from ganache to anvil
- Remove pysha3 dependency
- Remove python2 style super() call
- Remove OrderedAttributesMeta. From version 3.7 onward, dictionaries maintain the insertion order of their items.
- Require python >= 3.10 as the lowest version to install with [uv](https://github.com/astral-sh/uv)
- Switch from Sphinx to Google docstring format for readability
- Lint with [ruff](https://github.com/astral-sh/ruff)
- Add Github workflows (lint and test)
- Add pyproject.toml

## Shameless Plug
Written by [ConsenSys](https://consensys.net) for the world! :heart:
