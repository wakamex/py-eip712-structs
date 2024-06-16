"""EIP-712 Domain Separator."""

import eip712_structs

# allow camelCase
# ruff: noqa: N803
# pylint: disable=invalid-name
# allow missing class docstring
# pylint: disable=missing-class-docstring

def make_domain(name=None, version=None, chainId=None, verifyingContract=None, salt=None):
    """Create the standard EIP712Domain struct.

    Per the standard, if a value is not used then the parameter is omitted from the struct entirely.
    """
    if all(i is None for i in [name, version, chainId, verifyingContract, salt]):
        raise ValueError("At least one argument must be given.")

    class EIP712Domain(eip712_structs.EIP712Struct):
        pass

    kwargs = {}
    if name is not None:
        EIP712Domain.name = eip712_structs.String()  # type: ignore
        kwargs["name"] = str(name)
    if version is not None:
        EIP712Domain.version = eip712_structs.String()  # type: ignore
        kwargs["version"] = str(version)
    if chainId is not None:
        EIP712Domain.chainId = eip712_structs.Uint(256)  # type: ignore
        kwargs["chainId"] = int(chainId)
    if verifyingContract is not None:
        EIP712Domain.verifyingContract = eip712_structs.Address()  # type: ignore
        kwargs["verifyingContract"] = verifyingContract
    if salt is not None:
        EIP712Domain.salt = eip712_structs.Bytes(32)  # type: ignore
        kwargs["salt"] = salt

    return EIP712Domain(**kwargs)
