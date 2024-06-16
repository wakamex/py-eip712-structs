"""Test that chain parity works."""

import os

import pytest
from requests.exceptions import ConnectionError
from web3 import HTTPProvider, Web3

from eip712_structs import Address, Array, Boolean, Bytes, EIP712Struct, Int, String, Uint

# allow redefining ConnectionError
# pylint: disable=redefined-builtin
# allow lots of function arguments
# ruff: noqa: PLR0913
# pylint: disable=too-many-arguments
# allow lots of local variables
# pylint: disable=too-many-locals
# allow redefining outer name for fixtures
# pylint: disable=redefined-outer-name
# allow classes without docstrings
# ruff: noqa: D101
# pylint: disable=missing-class-docstring
# allow classes with no methods
# pylint: disable=too-few-public-methods


@pytest.fixture(scope="module")
def w3():
    """Provide a Web3 client to interact with a local chain."""
    client = Web3(HTTPProvider("http://localhost:11111"))
    client.eth.default_account = client.eth.accounts[0]
    return client


@pytest.fixture(scope="module")
def contract(w3):
    """Deploys the test contract to the local chain, and returns a Web3.py Contract to interact with it.

    Note this expects the contract to be compiled already.
    This project's docker-compose config pulls a solc container to do this for you.
    """
    base_path = "tests/contracts/build/TestContract"
    with open(f"{base_path}.abi", "r", encoding="utf-8") as f:
        abi = f.read()
    with open(f"{base_path}.bin", "r", encoding="utf-8") as f:
        bytecode = f.read()

    tmp_contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    deploy_hash = tmp_contract.constructor().transact()
    deploy_receipt = w3.eth.wait_for_transaction_receipt(deploy_hash)

    return w3.eth.contract(abi=abi, address=deploy_receipt.contractAddress)


def skip_this_module():
    """If we can't reach a local chain, then all tests in this module are skipped."""
    client = Web3(HTTPProvider("http://localhost:11111"))
    try:
        client.eth.accounts
    except ConnectionError:
        return True
    return False


# Implicitly adds this ``skipif`` mark to the tests below.
pytestmark = pytest.mark.skipif(skip_this_module(), reason="No accessible test chain.")


# These structs must match the struct in tests/contracts/hash_test_contract.sol
class Bar(EIP712Struct):
    bar_uint = Uint(256)


# TODO Add Array type (w/ appropriate test updates) to this struct.
class Foo(EIP712Struct):
    s = String()
    u_i = Uint(256)
    s_i = Int(8)
    a = Address()
    b = Boolean()
    bytes_30 = Bytes(30)
    dyn_bytes = Bytes()
    bar = Bar
    arr = Array(Bytes(1))


def get_chain_hash(contract, s, u_i, s_i, a, b, bytes_30, dyn_bytes, bar_uint, arr) -> bytes:
    """Use the contract to create and hash a Foo struct with the given parameters."""
    return contract.functions.hashFooStructFromParams(s, u_i, s_i, a, b, bytes_30, dyn_bytes, bar_uint, arr).call()


def test_encoded_types(contract):
    """Checks that the encoded types (and the respective hashes) of our structs match."""
    local_bar_sig = Bar.encode_type()
    remote_bar_sig = contract.functions.BarSig().call()
    assert local_bar_sig == remote_bar_sig

    local_foo_sig = Foo.encode_type()
    remote_foo_sig = contract.functions.FooSig().call()
    assert local_foo_sig == remote_foo_sig

    local_bar_hash = Bar.type_hash()
    remote_bar_hash = contract.functions.Bar_TYPEHASH().call()
    assert local_bar_hash == remote_bar_hash

    local_foo_hash = Foo.type_hash()
    remote_foo_hash = contract.functions.Foo_TYPEHASH().call()
    assert local_foo_hash == remote_foo_hash

    array_type = Array(Bytes(1))
    bytes_array = [os.urandom(1) for _ in range(5)]
    local_encoded_array = array_type.encode_value(bytes_array)
    remote_encoded_array = contract.functions.encodeBytes1Array(bytes_array).call()
    assert local_encoded_array == remote_encoded_array


def test_chain_hash_matches(contract):
    """Assert that the hashes we derive locally match the hashes derived on-chain."""
    # Initialize basic values
    s = "some string"
    u_i = 1234
    s_i = -7
    a = Web3.to_checksum_address(f"0x{os.urandom(20).hex()}")
    b = True
    bytes_30 = os.urandom(30)
    dyn_bytes = os.urandom(50)
    arr = [os.urandom(1) for _ in range(5)]

    # Initialize a Bar struct, and check it standalone
    bar_uint = 1337
    bar_struct = Bar(bar_uint=bar_uint)
    local_bar_hash = bar_struct.hash_struct()
    remote_bar_hash = contract.functions.hashBarStructFromParams(bar_uint).call()
    assert local_bar_hash == remote_bar_hash

    # Initialize a Foo struct (including the Bar struct above) and check the hashes
    foo_struct = Foo(s=s, u_i=u_i, s_i=s_i, a=a, b=b, bytes_30=bytes_30, dyn_bytes=dyn_bytes, bar=bar_struct, arr=arr)
    local_foo_hash = foo_struct.hash_struct()
    remote_foo_hash = get_chain_hash(contract, s, u_i, s_i, a, b, bytes_30, dyn_bytes, bar_uint, arr)
    assert local_foo_hash == remote_foo_hash
