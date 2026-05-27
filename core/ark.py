import random
import requests

_NOID_CHARS = '0123456789bcdfghjkmnpqrstvwxz'


def mint_ark(username, password, shoulder):
    """Mint a real ARK via the EZID API using the ERC profile."""
    url = f'https://ezid.cdlib.org/shoulder/{shoulder}'
    data_encoded = '_profile: erc'.encode('utf-8')
    response = requests.post(
        url,
        headers={'Content-Type': 'text/plain; charset=UTF-8'},
        data=data_encoded,
        auth=(username, password)
    )
    if response.status_code == 201:
        ark = response.text.strip()
        if ark.startswith("success: "):
            return ark[len("success: "):].strip()
        return ark
    return None


def fake_ark():
    """Generate a placeholder ARK for testing when EZID credentials are not provided."""
    noid = ''.join(random.choices(_NOID_CHARS, k=8))
    return f"ark:/FAKE/{noid}"


def get_ark(username, password, shoulder):
    """Mint a real ARK if credentials are provided, otherwise return a placeholder."""
    if username and password and shoulder:
        ark = mint_ark(username, password, shoulder)
        return ark if ark else "ERROR: ARK not minted"
    return fake_ark()


def child_ark(parent_ark):
    """Derive a child ARK by appending a locally-generated NOID qualifier to the parent ARK."""
    noid = ''.join(random.choices(_NOID_CHARS, k=8))
    return f"{parent_ark}/{noid}"
