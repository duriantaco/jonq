def _split_top_level(s: str, needle: str):
    n = len(needle)
    depth = 0
    in_sq = in_dq = False
    i = 0
    while i <= len(s) - n:
        ch = s[i]
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "(" and not in_sq and not in_dq:
            depth += 1
        elif ch == ")" and not in_sq and not in_dq:
            depth -= 1
        if depth == 0 and not in_sq and not in_dq and s[i : i + n].lower() == needle:
            return s[:i], s[i + n :]
        i += 1
    return None, None
