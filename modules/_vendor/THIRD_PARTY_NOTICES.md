# Third-Party Notices — modules/_vendor

This directory vendors two upstream Python packages for Computer Use UIA support.
This file records their upstream licenses verbatim as fetched from the upstream
repositories on 2026-08-31. It must ship with any redistribution that includes
the vendored trees.

## comtypes

- Upstream: https://github.com/enthought/comtypes
- License: MIT (upstream LICENSE.txt, fetched from `master` on 2026-08-31)
- Vendored version marker: `comtypes/gen` pinned type-library generation used
  by `tools/run_localcomet_desktop_sidecar.py` sys.path bootstrap.

```
This software is OSI Certified Open Source Software.
OSI Certified is a certification mark of the Open Source Initiative.

Copyright (c) 2006-2013, Thomas Heller.
Copyright (c) 2014, Comtypes Developers.
All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

## uiautomation

- Upstream: https://github.com/yinkaisheng/Python-UIAutomation-for-Windows
- License: Apache License 2.0 (upstream LICENSE, fetched from `master` on
  2026-08-31; copyright "Copyright Yinkaisheng" per upstream appendix).
- Vendored files: `uiautomation.py` and the helper modules it imports
  (`_vendor/uiautomation/*.py`).

The full Apache License 2.0 text applies. Upstream appendix notice:

```
Copyright Yinkaisheng

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

The complete Apache License 2.0 text is available upstream at
https://www.apache.org/licenses/LICENSE-2.0.txt and is reproduced in the
LocalComet provenance inventory (`audit/provenance_inventory_current_*.json`)
references. A local full-text copy ships as
`modules/_vendor/uiautomation/LICENSE.APACHE-2.0` in this repository.
