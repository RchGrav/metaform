# 2 only adds a2a_asks, 3 only a2a_peers and a2a_exchanges, 4 only a2a_exchanges' `asked`, the open question at the
# Address whose answer goes back to the peer, 5 only its `sending`, when a sender claimed that answer; each may be
# empty, so every earlier version still reads the rest.
TABLES = Tables(version=5,