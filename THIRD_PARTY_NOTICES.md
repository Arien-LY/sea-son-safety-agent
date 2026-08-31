# Third-party notices

## Windows competition distribution

The portable package preserves CPython's license and the installed Python distributions' original license files
under `_internal/licenses`, plus the original runtime distribution metadata. The existing `hello-agents==0.2.9`
distribution declares **CC-BY-NC-SA-4.0**; this competition build is not a promise of commercial distribution rights.
No third-party framework is modified. Frontend runtime package licenses are also copied in full; the license omitted
from the @vue/devtools-api 6.6.4 npm tarball is supplied from its exact upstream tag in
`desktop/licenses/vue-devtools-api-6.6.4.txt`.

## markdown-it 15.0.1

Source: <https://github.com/markdown-it/markdown-it>

License: MIT

Copyright (c) 2014 Vitaly Puzrin, Alex Kocharin.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of
the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

The package manager also installs markdown-it's declared runtime dependencies. Their license identifiers are kept
in `frontend/package-lock.json`: argparse (PSF-2.0), entities (BSD-2-Clause), linkify-it (MIT), mdurl (MIT),
punycode.js (MIT), and uc.micro (MIT).
