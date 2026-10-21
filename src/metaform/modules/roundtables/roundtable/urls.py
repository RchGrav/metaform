"""Advertised HTTP URLs, kept separate from the host used to bind a listener."""


def http_base(host: str, port: int) -> str:
    """An HTTP base URL for a bind host, with brackets around IPv6 literals."""
    authority = f'[{host}]' if ':' in host else host
    return f'http://{authority}:{port}'
