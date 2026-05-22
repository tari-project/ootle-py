"""Resource package for the vendored ``ootle_wasm_bg.wasm`` blob.

The blob and its ``VERSION`` metadata are loaded via
``importlib.resources.files`` so they work from both source trees and zipped
wheels. Refresh with ``make update-wasm WASM_VERSION=x.y.z``.
"""
