"""Hide the top-level nvidia package from this process, to exercise the CPU fallback when CUDA libraries are missing.

Import this module before anything else in the process under test:
    import hide_nvidia_wheels  # noqa: F401
It only affects the importing process; the shared .venv is untouched.
"""
import importlib.machinery
import sys


class _HideNvidiaWheels:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'nvidia':
            return importlib.machinery.ModuleSpec(fullname, None, is_package=True)
        return None


sys.meta_path.insert(0, _HideNvidiaWheels())
