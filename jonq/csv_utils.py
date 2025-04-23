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
    """
    Flatten nested JSON structures for CSV output.
    
    Args:
        data: The JSON data to flatten
        parent_key: The parent key for nested structures
        sep: The separator to use between nested keys
        use_fast: If True, will attempt to use jonq_fast if available
    
    Returns:
        A flattened dictionary
    """
    if use_fast:
        try:
            import jonq_fast
            return jonq_fast.flatten(data, sep)
        except ImportError:
            pass
    
    items = []
    
    if isinstance(data, dict):
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, (dict, list)):
                items.extend(flatten_json(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
            if isinstance(v, (dict, list)):
                items.extend(flatten_json(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
    else:
        items.append((parent_key, data))
        
    return dict(items)

def json_to_csv(json_data, use_fast=False):
    """
    Convert JSON to CSV format.
    
    Args:
        json_data: The JSON data to convert
        use_fast: If True, will use jonq_fast for flattening if available
    """
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