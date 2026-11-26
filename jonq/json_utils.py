try:
    import orjson as _json_impl

    def dumps(obj):
        return _json_impl.dumps(obj).decode("utf-8")

    def loads(json_str):
        return _json_impl.loads(json_str)

except ImportError:
    import json as _json_impl

    def dumps(obj):
        return _json_impl.dumps(obj, ensure_ascii=False, separators=(",", ":"))

    def loads(json_str):
        return _json_impl.loads(json_str)


__all__ = ["dumps", "loads"]
