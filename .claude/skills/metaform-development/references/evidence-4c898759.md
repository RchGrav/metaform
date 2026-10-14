The fresh-home check passes. The failure is in my test: it loosened the files to 0755, and tightening deliberately keeps an executable's owner x bit. Loosening files to 0644 instead.

E         AssertionError: assert {'/tmp/pytest... '0o700', ...} == {'/tmp/pytest... '0o600', ...}
E         {'/tmp/pytest-of-rich/.../home/run/web-project': '0o700'} != {'/tmp/pytest-of-rich/.../home/run/web-project': '0o600'}

Done 3: home.make_private() makes a missing home 0700; a home with group or other bits and no 'home_private' meta is walked once, stripping group/other bits from every folder and file (executables keep the owner's x, symlinks untouched), then 'home_private' is recorded.