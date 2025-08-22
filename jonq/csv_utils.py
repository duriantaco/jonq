import csv
import io

try:
    import orjson as _json_impl

    def _dumps(obj):
        return _json_impl.dumps(obj).decode()
    
    _loads = _json_impl.loads

except ModuleNotFoundError:
    import json as _json_impl

    _dumps = _json_impl.dumps
    _loads = _json_impl.loads

def flatten_json(data, parent_key='', sep='.', use_fast=False):
    
    items = []
    
    if isinstance(data, dict):
        for k, v in data.items():
            if parent_key:
                new_key = parent_key + sep + k
            else:
                new_key = k
            if isinstance(v, (dict, list)):
                items.extend(flatten_json(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            if parent_key:
                new_key = parent_key + sep + str(i)
            else:
                new_key = str(i)
            if isinstance(v, (dict, list)):
                items.extend(flatten_json(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
    else:
        items.append((parent_key, data))
        
    return dict(items)

def json_to_csv(json_data, use_fast=False):

    if isinstance(json_data, str):
        try:
            data = _loads(json_data)
        except Exception:
            return json_data
    else:
        data = json_data
    
    if not isinstance(data, list):
        data = [data]
    
    if not data:
        return ""
    
    flattened_data = []
    for item in data:
        if isinstance(item, dict):
            flattened = flatten_json(item, sep='.', use_fast=use_fast)
            if not flattened and isinstance(item, dict):
                flattened = {"_empty": ""}
            flattened_data.append(flattened)
        else:
            flattened_data.append({"value": item})
    
    fieldnames = set()
    for item in flattened_data:
        fieldnames.update(item.keys())
    
    if "_empty" in fieldnames and len(fieldnames) > 1:
        fieldnames.remove("_empty")
    
    fieldnames = sorted(list(fieldnames))
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    
    for item in flattened_data:
        row = {}
        for key, value in item.items():
            if key == "_empty" and len(fieldnames) > 0 and "_empty" not in fieldnames:
                continue
            if isinstance(value, (dict, list)):
                row[key] = _dumps(value)
            else:
                row[key] = value
        writer.writerow(row)
    
    return output.getvalue()