"""Provider adapters.

Each provider module exposes `call(...)` and `call_json(...)` functions.
Router dispatches based on the provider's `type` field in config.
"""
