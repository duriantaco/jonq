try:
    import orjson as _json_impl

    def dumps(obj) -> str:
        return _json_impl.dumps(obj).decode('utf-8')

    def loads(json_str):
        return _json_impl.loads(json_str)

except ImportError:
    import json as _json_impl

    def dumps(obj) -> str:
        return _json_impl.dumps(obj)

    def loads(json_str):
        return _json_impl.loads(json_str)

__all__ = ['dumps', 'loads']