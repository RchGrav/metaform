"""The packet module ships disabled, so a process that has not enabled it holds none of its settings. These tests
import the module, which declares its setting for the whole test process; the setting is taken out again when they
are done, so the tests that run after them see the settings of a process where the module is off."""
from __future__ import annotations

import importlib

import pytest

from metaform import settings


@pytest.fixture(autouse=True, scope='package')
def packet_settings_only_here():
    from metaform.modules import packet
    if any(key not in settings.SCHEMA for key in packet.EVIDENCE):
        importlib.reload(packet)  # declares packet_evidence again
    yield
    for key in packet.EVIDENCE:
        settings.SCHEMA.pop(key, None)
