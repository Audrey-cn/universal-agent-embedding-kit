"""Second scenario pack: 20 additional real-world scenarios (categories 11-30)."""

from src.scenario_benchmark import RealScenario, ScenarioCheck

SCENARIO_PACK_2 = (
    RealScenario(
        scenario_id="query_users",
        title="Query users older than a given age from a list of dicts",
        category="database-query",
        ambiguity="Empty list when no users match; 'age' key always exists.",
        checks=(
            ScenarioCheck("correctness", "query_users", [[{'name': 'A', 'age': 25}, {'name': 'B', 'age': 30}], 20], [{'name': 'A', 'age': 25}, {'name': 'B', 'age': 30}]),
            ScenarioCheck("correctness", "query_users", [[{'name': 'A', 'age': 25}, {'name': 'B', 'age': 30}], 28], [{'name': 'B', 'age': 30}]),
            ScenarioCheck("completeness", "query_users", [[{'name': 'A', 'age': 25}], 30], []),
            ScenarioCheck("robustness", "query_users", [[], 20], []),
        ),
    ),

    RealScenario(
        scenario_id="find_by_ext",
        title="Find files by extension in nested filesystem dict",
        category="filesystem-io",
        ambiguity="Directories are dicts with optional 'files' key.",
        checks=(
            ScenarioCheck("correctness", "find_by_ext", [{'files': [{'name': 'a.py'}, {'name': 'b.txt'}], 'sub': {'files': [{'name': 'c.py'}]}}, '.py'], ['a.py', 'c.py']),
            ScenarioCheck("correctness", "find_by_ext", [{'files': [{'name': 'a.py'}], 'sub': {'files': [{'name': 'a.md'}]}}, '.md'], ['a.md']),
            ScenarioCheck("completeness", "find_by_ext", [{'files': []}, '.py'], []),
            ScenarioCheck("robustness", "find_by_ext", [{}, '.py'], []),
            ScenarioCheck("robustness", "find_by_ext", [None, '.py'], []),
        ),
    ),

    RealScenario(
        scenario_id="fetch_all_pages",
        title="Collect all items across pages via fetch_page(limit, offset)",
        category="api-client",
        ambiguity="fetch_page returns [] when exhausted.",
        checks=(
            ScenarioCheck("correctness", "fetch_all_pages", [2, 5], [0, 1, 2, 3, 4]),
            ScenarioCheck("correctness", "fetch_all_pages", [5, 3], [0, 1, 2]),
            ScenarioCheck("completeness", "fetch_all_pages", [2, 0], []),
            ScenarioCheck("robustness", "fetch_all_pages", [3, 0], []),
        ),
    ),

    RealScenario(
        scenario_id="next_weekday",
        title="Given YYYY-MM-DD return next weekday (0=Mon..6=Sun)",
        category="datetime-handling",
        ambiguity="If input matches return 7 days later.",
        checks=(
            ScenarioCheck("correctness", "next_weekday", ['2026-06-15', 0], '2026-06-22'),
            ScenarioCheck("correctness", "next_weekday", ['2026-06-15', 4], '2026-06-19'),
            ScenarioCheck("correctness", "next_weekday", ['2026-06-20', 6], '2026-06-21'),
            ScenarioCheck("completeness", "next_weekday", ['2026-06-17', 2], '2026-06-24'),
            ScenarioCheck("robustness", "next_weekday", ['2026-12-31', 0], '2027-01-04'),
        ),
    ),

    RealScenario(
        scenario_id="csv_column_stats",
        title="Parse CSV, compute min/max/avg for a named column",
        category="csv-processing",
        ambiguity="Comma delimiter no quoting; missing=0.",
        checks=(
            ScenarioCheck("correctness", "col_stats", ['name,val\\na,10\\nb,20\\nc,30', 'val'], [10.0, 30.0, 20.0]),
            ScenarioCheck("correctness", "col_stats", ['x,y\\n1,2\\n3,4', 'x'], [1.0, 3.0, 2.0]),
            ScenarioCheck("completeness", "col_stats", ['h,v\\n', 'v'], [0.0, 0.0, 0.0]),
            ScenarioCheck("robustness", "col_stats", ['a,b\\nx,\\ny,5', 'b'], [0.0, 5.0, 2.5]),
        ),
    ),

    RealScenario(
        scenario_id="lru_cache",
        title="LRU cache with set(key,val) get(key) and fixed capacity",
        category="caching",
        ambiguity="set on existing key refreshes; get missing = None.",
        checks=(
            ScenarioCheck("correctness", "run_lru", [2, ['set(a,1)', 'set(b,2)', 'get(a)']], [1]),
            ScenarioCheck("correctness", "run_lru", [3, ['set(a,1)', 'set(b,2)', 'set(c,3)', 'get(b)']], [2]),
            ScenarioCheck("completeness", "run_lru", [2, ['set(a,1)', 'set(b,2)', 'set(c,3)', 'get(a)', 'get(b)']], [None, 2]),
            ScenarioCheck("robustness", "run_lru", [1, ['set(a,1)', 'set(b,2)', 'get(a)', 'get(b)']], [None, 2]),
        ),
    ),

    RealScenario(
        scenario_id="parse_logs",
        title="Parse LEVEL:timestamp:message and filter by level",
        category="regex-parsing",
        ambiguity="Exactly one colon-delimited level; message may contain colons.",
        checks=(
            ScenarioCheck("correctness", "parse_logs", [['INFO:20260601:started'], 'INFO'], ['started']),
            ScenarioCheck("correctness", "parse_logs", [['ERROR:20260601:fail:timeout'], 'ERROR'], ['fail:timeout']),
            ScenarioCheck("completeness", "parse_logs", [['INFO:20260601:a', 'WARN:20260602:b'], 'WARN'], ['b']),
            ScenarioCheck("robustness", "parse_logs", [[], 'INFO'], []),
            ScenarioCheck("robustness", "parse_logs", [['DEBUG:2026-06:dbg'], 'INFO'], []),
        ),
    ),

    RealScenario(
        scenario_id="url_parser",
        title="Parse URL into (scheme, host, path, query_dict)",
        category="encoding",
        ambiguity="May have no query/path/scheme (default http).",
        checks=(
            ScenarioCheck("correctness", "parse_url", ['https://example.com/path?a=1&b=2'], ['https', 'example.com', '/path', {'a': '1', 'b': '2'}]),
            ScenarioCheck("correctness", "parse_url", ['http://x.y/z'], ['http', 'x.y', '/z', {}]),
            ScenarioCheck("completeness", "parse_url", ['example.com'], ['http', 'example.com', '', {}]),
            ScenarioCheck("robustness", "parse_url", [''], ['', '', '', {}]),
        ),
    ),

    RealScenario(
        scenario_id="bfs_shortest_path",
        title="Shortest path length in unweighted graph (adjacency dict)",
        category="graph-traversal",
        ambiguity="No path = -1; start==end = 0.",
        checks=(
            ScenarioCheck("correctness", "shortest_path", [{'A': ['B'], 'B': ['A', 'C'], 'C': ['B']}, 'A', 'C'], 2),
            ScenarioCheck("correctness", "shortest_path", [{'A': ['B'], 'B': ['A']}, 'A', 'A'], 0),
            ScenarioCheck("completeness", "shortest_path", [{'A': ['B'], 'B': ['A']}, 'A', 'C'], -1),
            ScenarioCheck("robustness", "shortest_path", [{}, 'A', 'B'], -1),
        ),
    ),

    RealScenario(
        scenario_id="batch_process",
        title="Split list into chunks of size N and apply a function",
        category="batch-processing",
        ambiguity="Last chunk smaller; empty list returns []; N<=0 returns [].",
        checks=(
            ScenarioCheck("correctness", "batch_process", ['sum', [1, 2, 3, 4, 5], 2], [3, 7, 5]),
            ScenarioCheck("correctness", "batch_process", ['len', [1, 2], 3], [2]),
            ScenarioCheck("completeness", "batch_process", ['sum', [], 2], []),
            ScenarioCheck("robustness", "batch_process", ['sum', [1], 0], []),
        ),
    ),

    RealScenario(
        scenario_id="rate_limiter",
        title="Token bucket: allow_request(max_burst, refill_rate, tokens, delta)",
        category="rate-limiter",
        ambiguity="Refill capped at max_burst; tokens float; negative tokens reset.",
        checks=(
            ScenarioCheck("correctness", "allow_request", [10, 5, 8, 1.0], [True, 9.0]),
            ScenarioCheck("correctness", "allow_request", [10, 5, 0, 1.0], [True, 4.0]),
            ScenarioCheck("completeness", "allow_request", [10, 5, 9, 2.0], [True, 9.0]),
            ScenarioCheck("robustness", "allow_request", [10, 5, -1, 1.0], [True, 4.0]),
        ),
    ),

    RealScenario(
        scenario_id="dependency_order",
        title="Topologically sort DAG {node: [deps]}",
        category="dependency-resolver",
        ambiguity="Missing dep = no deps; cycle returns [].",
        checks=(
            ScenarioCheck("correctness", "topo_sort", [{'A': [], 'B': ['A']}], ['A', 'B']),
            ScenarioCheck("correctness", "topo_sort", [{'A': ['B'], 'B': []}], ['B', 'A']),
            ScenarioCheck("completeness", "topo_sort", [{'A': ['B'], 'B': ['C']}], ['C', 'B', 'A']),
            ScenarioCheck("robustness", "topo_sort", [{'A': ['A']}], []),
            ScenarioCheck("robustness", "topo_sort", [{}], []),
        ),
    ),

    RealScenario(
        scenario_id="circuit_breaker",
        title="Circuit breaker: opens after N failures",
        category="error-handling",
        ambiguity="Call count resets on success; open raises CircuitOpen.",
        checks=(
            ScenarioCheck("correctness", "call_wrapper", [[['call', 'ok'], ['status']]], ['ok', ['closed', 0]]),
            ScenarioCheck("correctness", "call_wrapper", [[['call', 'fail'], ['call', 'fail'], ['call', 'fail'], ['status']]], ['ok', 'ok', 'ok', ['open', 3]]),
            ScenarioCheck("completeness", "call_wrapper", [[['call', 'fail'], ['call', 'fail'], ['call', 'ok'], ['status']]], ['ok', 'ok', 'ok', ['closed', 0]]),
            ScenarioCheck("robustness", "call_wrapper", [[['noop']]], {'msg': 'no-op'}),
        ),
    ),

    RealScenario(
        scenario_id="event_emitter",
        title="Simple pub/sub: on(event,fn_args) trigger(event) off(event)",
        category="event-emitter",
        ambiguity="off non-existent event = no-op.",
        checks=(
            ScenarioCheck("correctness", "run_emitter", [[['on', 'add', [1, 2]], ['trigger', 'add']]], [[1, 2]]),
            ScenarioCheck("correctness", "run_emitter", [[['on', 'add', [3]], ['off', 'add'], ['trigger', 'add']]], []),
            ScenarioCheck("completeness", "run_emitter", [[['on', 'a', [10]], ['on', 'a', [20]], ['trigger', 'a']]], [[10], [20]]),
            ScenarioCheck("robustness", "run_emitter", [[['off', 'x'], ['trigger', 'x']]], []),
        ),
    ),

    RealScenario(
        scenario_id="template_render",
        title="Replace {{placeholders}} with values",
        category="template-engine",
        ambiguity="Unknown placeholders remain; no nested braces.",
        checks=(
            ScenarioCheck("correctness", "render", ['Hello, {{name}}!', {'name': 'World'}], 'Hello, World!'),
            ScenarioCheck("completeness", "render", ['{{a}} and {{b}}', {'a': '1'}], '1 and {{b}}'),
            ScenarioCheck("robustness", "render", ['no braces', {'x': 'y'}], 'no braces'),
            ScenarioCheck("robustness", "render", ['', {}], ''),
        ),
    ),

    RealScenario(
        scenario_id="validation_chain",
        title="Validators returning None (ok) or error string",
        category="validation-pipeline",
        ambiguity="First error stops (fail-fast); empty chain passes all.",
        checks=(
            ScenarioCheck("correctness", "validate", [['min_len:3', 'has_digit'], 'ab3'], None),
            ScenarioCheck("correctness", "validate", [['min_len:3'], 'ab'], 'too_short: min 3'),
            ScenarioCheck("completeness", "validate", [['has_digit'], 'abc'], 'missing_digit'),
            ScenarioCheck("robustness", "validate", [[], 'anything'], None),
        ),
    ),

    RealScenario(
        scenario_id="cursor_pagination",
        title="Traverse items via (items, next_cursor) tuples",
        category="pagination",
        ambiguity="next_cursor=None = end; cursor='' = start.",
        checks=(
            ScenarioCheck("correctness", "paginate_all", ['', 2], [0, 1, 2]),
            ScenarioCheck("correctness", "paginate_all", ['', 5], [0, 1, 2]),
            ScenarioCheck("completeness", "paginate_all", ['', 10], [0, 1, 2]),
            ScenarioCheck("robustness", "paginate_all", [None, 2], []),
        ),
    ),

    RealScenario(
        scenario_id="text_diff",
        title="Line-level diff of two multi-line strings",
        category="text-diff",
        ambiguity="Output: [' ',line]=same ['-',line]=removed ['+',line]=added.",
        checks=(
            ScenarioCheck("correctness", "text_diff", ['a\nb', 'a\nc'], [[' ', 'a'], ['+', 'c'], ['-', 'b']]),
            ScenarioCheck("correctness", "text_diff", ['a', 'a'], [[' ', 'a']]),
            ScenarioCheck("completeness", "text_diff", ['', 'a'], [['+', 'a']]),
            ScenarioCheck("robustness", "text_diff", ['', ''], []),
        ),
    ),

    RealScenario(
        scenario_id="leaderboard",
        title="Leaderboard: add_score(player,score) top(n) rank(player)",
        category="sorting-ranking",
        ambiguity="Ties share rank; unknown player = None.",
        checks=(
            ScenarioCheck("correctness", "run_leaderboard", [[['add', 'A', 100], ['add', 'B', 200], ['top', 1]]], [[['B', 200]]]),
            ScenarioCheck("correctness", "run_leaderboard", [[['add', 'A', 100], ['add', 'B', 100], ['top', 2]]], [[['A', 100], ['B', 100]]]),
            ScenarioCheck("completeness", "run_leaderboard", [[['add', 'A', 50], ['rank', 'A']]], [1]),
            ScenarioCheck("robustness", "run_leaderboard", [[['rank', 'X']]], [None]),
        ),
    ),

    RealScenario(
        scenario_id="cron_check",
        title="Check if hour matches a cron expression",
        category="cron-parser",
        ambiguity="* = any; range 0-5 supported.",
        checks=(
            ScenarioCheck("correctness", "cron_matches", ['* 9 * * *', 9], True),
            ScenarioCheck("correctness", "cron_matches", ['* 9 * * *', 10], False),
            ScenarioCheck("completeness", "cron_matches", ['* * * * *', 0], True),
            ScenarioCheck("robustness", "cron_matches", ['* 0-5 * * *', 2], True),
            ScenarioCheck("robustness", "cron_matches", ['* 0-5 * * *', 7], False),
        ),
    ),

)

REFERENCE_PACK_2 = {
    "query_users": (
        "def query_users(users, min_age):\n    return [u for u in users if u['age'] > min_age]\n"
    ),

    "find_by_ext": (
        "def find_by_ext(node, ext):\n    if not isinstance(node, dict):\n        return []\n    result = []\n    for f in node.get('files', []):\n        if f.get('name', '').endswith(ext):\n            result.append(f['name'])\n    for key, val in node.items():\n        if key != 'files' and isinstance(val, dict):\n            result.extend(find_by_ext(val, ext))\n    return sorted(result)\n"
    ),

    "fetch_all_pages": (
        "def fetch_all_pages(page_size, total):\n    results, offset = [], 0\n    while True:\n        batch = list(range(offset, min(offset + page_size, total)))\n        if not batch:\n            break\n        results.extend(batch)\n        offset += page_size\n    return results\n"
    ),

    "next_weekday": (
        "from datetime import datetime, timedelta\ndef next_weekday(date_str, target_wd):\n    dt = datetime.strptime(date_str, '%Y-%m-%d')\n    days_ahead = (target_wd - dt.weekday()) % 7\n    if days_ahead == 0:\n        days_ahead = 7\n    return (dt + timedelta(days=days_ahead)).strftime('%Y-%m-%d')\n"
    ),

    "csv_column_stats": (
        "def col_stats(csv_str, col_name):\n    lines = csv_str.strip().split(r\"\\n\")\n    lines = [l for l in lines if l.strip()]\n    if len(lines) < 2:\n        return [0.0, 0.0, 0.0]\n    header = lines[0].split(',')\n    if col_name not in header:\n        return [0.0, 0.0, 0.0]\n    idx = header.index(col_name)\n    vals = []\n    for row in lines[1:]:\n        parts = row.split(',')\n        if idx < len(parts) and parts[idx].strip():\n            vals.append(float(parts[idx]))\n        else:\n            vals.append(0.0)\n    return [min(vals), max(vals), sum(vals)/len(vals)]\n"
    ),

    "lru_cache": (
        "def run_lru(capacity, ops):\n    cache, order = {}, []\n    results = []\n    for op in ops:\n        if op.startswith('set('):\n            key, val = op[4:-1].split(',')\n            if key in cache:\n                order.remove(key)\n            elif len(cache) >= capacity:\n                evict = order.pop(0)\n                del cache[evict]\n            cache[key] = int(val)\n            order.append(key)\n        elif op.startswith('get('):\n            key = op[4:-1]\n            if key in cache:\n                order.remove(key)\n                order.append(key)\n                results.append(cache[key])\n            else:\n                results.append(None)\n    return results\n"
    ),

    "parse_logs": (
        "import re\ndef parse_logs(lines, target_level):\n    results = []\n    pat = re.compile(r'^([A-Z]+):(.*?):(.*)$')\n    for line in lines:\n        m = pat.match(line)\n        if m and m.group(1) == target_level:\n            results.append(m.group(3))\n    return results\n"
    ),

    "url_parser": (
        "from urllib.parse import urlparse, parse_qs\ndef parse_url(url):\n    if not url:\n        return ['', '', '', {}]\n    if '://' not in url:\n        url = 'http://' + url\n    parsed = urlparse(url)\n    qs = {k: v[0] for k, v in parse_qs(parsed.query).items()} if parsed.query else {}\n    return [parsed.scheme, parsed.hostname or '', parsed.path or '', qs]\n"
    ),

    "bfs_shortest_path": (
        "from collections import deque\ndef shortest_path(graph, start, end):\n    if start == end:\n        return 0\n    visited = {start}\n    q = deque([(start, 0)])\n    while q:\n        node, dist = q.popleft()\n        for neighbor in graph.get(node, []):\n            if neighbor == end:\n                return dist + 1\n            if neighbor not in visited:\n                visited.add(neighbor)\n                q.append((neighbor, dist + 1))\n    return -1\n"
    ),

    "batch_process": (
        "def batch_process(fn, items, chunk_size):\n    if chunk_size <= 0 or not items:\n        return []\n    import builtins\n    f = getattr(builtins, fn)\n    return [f(items[i:i+chunk_size]) for i in range(0, len(items), chunk_size)]\n"
    ),

    "rate_limiter": (
        "def allow_request(max_burst, refill_rate, tokens, delta):\n    if tokens < 0:\n        tokens = 0\n    tokens = min(tokens + refill_rate * delta, max_burst)\n    if tokens >= 1.0:\n        tokens -= 1.0\n        return [True, tokens]\n    return [False, tokens]\n"
    ),

    "dependency_order": (
        "def topo_sort(graph):\n    visited = set()\n    result = []\n    temp = set()\n    def dfs(node):\n        if node in temp:\n            return False\n        if node in visited:\n            return True\n        temp.add(node)\n        for dep in graph.get(node, []):\n            if not dfs(dep):\n                return False\n        temp.remove(node)\n        visited.add(node)\n        result.append(node)\n        return True\n    for node in list(graph.keys()):\n        if node not in visited:\n            if not dfs(node):\n                return []\n    return result\n"
    ),

    "circuit_breaker": (
        "def call_wrapper(ops):\n    failures, threshold = 0, 2\n    open_state = False\n    results = []\n    for op in ops:\n        if op[0] == 'call':\n            if open_state:\n                results.append('blocked')\n                continue\n            if op[1] == 'fail':\n                failures += 1\n                if failures > threshold:\n                    open_state = True\n            else:\n                failures = 0\n            results.append('ok')\n        elif op[0] == 'status':\n            results.append(['open' if open_state else 'closed', failures])\n        elif op[0] == 'noop':\n            pass\n    return results if results else {'msg': 'no-op'}\n"
    ),

    "event_emitter": (
        "def run_emitter(ops):\n    handlers = {}\n    results = []\n    for op in ops:\n        if op[0] == 'on':\n            name, args = op[1], op[2]\n            if name not in handlers:\n                handlers[name] = []\n            handlers[name].append(args)\n        elif op[0] == 'off':\n            handlers.pop(op[1], None)\n        elif op[0] == 'trigger':\n            for h in handlers.get(op[1], []):\n                results.append(h)\n    return results\n"
    ),

    "template_render": (
        "import re\ndef render(template, values):\n    def repl(m):\n        key = m.group(1)\n        return str(values.get(key, m.group(0)))\n    return re.sub(r'\\{\\{(.*?)\\}\\}', repl, template)\n"
    ),

    "validation_chain": (
        "def validate(rules, value):\n    for rule in rules:\n        if rule == 'has_digit':\n            if not any(c.isdigit() for c in value):\n                return 'missing_digit'\n        elif rule.startswith('min_len:'):\n            n = int(rule.split(':')[1])\n            if len(value) < n:\n                return f'too_short: min {n}'\n    return None\n"
    ),

    "cursor_pagination": (
        "def paginate_all(cursor, page_size):\n    if cursor is None:\n        return []\n    all_items = [0, 1, 2]\n    if cursor == '':\n        cursor_i = 0\n    else:\n        cursor_i = int(cursor)\n    items = []\n    while cursor_i < len(all_items):\n        items.extend(all_items[cursor_i:cursor_i+page_size])\n        cursor_i += page_size\n    return list(items)\n"
    ),

    "text_diff": (
        "def text_diff(a, b):\n    lines_a = a.splitlines() if a else []\n    lines_b = b.splitlines() if b else []\n    result = []\n    i = j = 0\n    while i < len(lines_a) or j < len(lines_b):\n        if i < len(lines_a) and j < len(lines_b) and lines_a[i] == lines_b[j]:\n            result.append([' ', lines_a[i]])\n            i += 1\n            j += 1\n        elif j < len(lines_b):\n            result.append(['+', lines_b[j]])\n            j += 1\n        else:\n            result.append(['-', lines_a[i]])\n            i += 1\n    return result\n"
    ),

    "leaderboard": (
        "def run_leaderboard(ops):\n    scores = {}\n    results = []\n    for op in ops:\n        if op[0] == 'add':\n            scores[op[1]] = op[2]\n        elif op[0] == 'top':\n            sorted_players = sorted(scores.items(), key=lambda x: -x[1])\n            results.append([[p, s] for p, s in sorted_players[:op[1]]])\n        elif op[0] == 'rank':\n            sorted_players = sorted(scores.items(), key=lambda x: -x[1])\n            for i, (p, _) in enumerate(sorted_players):\n                if p == op[1]:\n                    results.append(i + 1)\n                    break\n            else:\n                results.append(None)\n    return results\n"
    ),

    "cron_check": (
        "def cron_matches(expr, hour):\n    parts = expr.split()\n    if len(parts) < 5:\n        return False\n    hour_field = parts[1]\n    if hour_field == '*':\n        return True\n    if '-' in hour_field:\n        lo, hi = hour_field.split('-')\n        return int(lo) <= hour <= int(hi)\n    return int(hour_field) == hour\n"
    ),

}

FLAWED_PACK_2 = {
    "query_users": (
        "def query_users(users, min_age):\n    return [u for u in users if u['age'] >= min_age]\n"
    ),

    "find_by_ext": (
        "def find_by_ext(node, ext):\n    if not isinstance(node, dict):\n        return []\n    result = []\n    for f in node.get('files', []):\n        if f.get('name', '').endswith(ext):\n            result.append(f['name'])\n    return result\n"
    ),

    "fetch_all_pages": (
        "def fetch_all_pages(page_size, total):\n    return list(range(0, min(page_size, total)))\n"
    ),

    "next_weekday": (
        "from datetime import datetime, timedelta\ndef next_weekday(date_str, target_wd):\n    dt = datetime.strptime(date_str, '%Y-%m-%d')\n    days_ahead = (target_wd - dt.weekday()) % 7\n    return (dt + timedelta(days=days_ahead)).strftime('%Y-%m-%d')\n"
    ),

    "csv_column_stats": (
        "def col_stats(csv_str, col_name):\n    lines = csv_str.strip().split(r\"\\n\")\n    if len(lines) < 2:\n        return [0.0, 0.0, 0.0]\n    header = lines[0].split(',')\n    idx = header.index(col_name)\n    vals = [float(row.split(',')[idx]) for row in lines[1:] if row]\n    return [min(vals), max(vals), sum(vals)/len(vals)]\n"
    ),

    "lru_cache": (
        "def run_lru(capacity, ops):\n    cache, order = {}, []\n    results = []\n    for op in ops:\n        if op.startswith('set('):\n            key, val = op[4:-1].split(',')\n            if key not in cache:\n                if len(cache) >= capacity:\n                    evict = order.pop(0)\n                    del cache[evict]\n                order.append(key)\n            cache[key] = int(val)\n        elif op.startswith('get('):\n            key = op[4:-1]\n            results.append(cache.get(key))\n    return results\n"
    ),

    "parse_logs": (
        "def parse_logs(lines, target_level):\n    results = []\n    for line in lines:\n        parts = line.split(':') if line else []\n        if len(parts) >= 3 and parts[0] == target_level:\n            results.append(':'.join(parts[2:]))\n    return results\n"
    ),

    "url_parser": (
        "def parse_url(url):\n    if not url:\n        return ('', '', '', {})\n    scheme = 'http'\n    rest = url\n    if '://' in url:\n        scheme, rest = url.split('://', 1)\n    if '/' in rest:\n        host, path = rest.split('/', 1)\n        path = '/' + path\n    else:\n        host, path = rest, ''\n    return [scheme, host, path, {}]\n"
    ),

    "bfs_shortest_path": (
        "def shortest_path(graph, start, end):\n    if start == end:\n        return 0\n    visited = set()\n    stack = [(start, 0)]\n    while stack:\n        node, dist = stack.pop()\n        if node in visited:\n            continue\n        visited.add(node)\n        for neighbor in graph.get(node, []):\n            if neighbor == end:\n                return dist + 1\n            stack.append((neighbor, dist + 1))\n    return -1\n"
    ),

    "batch_process": (
        "def batch_process(fn, items, chunk_size):\n    if not items:\n        return []\n    import builtins\n    f = getattr(builtins, fn)\n    return [f(items[i:i+chunk_size]) for i in range(0, len(items), chunk_size)]\n"
    ),

    "rate_limiter": (
        "def allow_request(max_burst, refill_rate, tokens, delta):\n    if tokens >= 1.0:\n        return [True, tokens - 1.0]\n    return [False, tokens]\n"
    ),

    "dependency_order": (
        "def topo_sort(graph):\n    result = []\n    for node in graph:\n        for dep in graph[node]:\n            if dep not in result:\n                result.append(dep)\n        if node not in result:\n            result.append(node)\n    return result\n"
    ),

    "circuit_breaker": (
        "def call_wrapper(ops):\n    failures, threshold = 0, 2\n    open_state = False\n    results = []\n    for op in ops:\n        if op[0] == 'call':\n            if op[1] == 'fail':\n                failures += 1\n                if failures > threshold:\n                    open_state = True\n            results.append('ok')\n        elif op[0] == 'status':\n            results.append(['open' if open_state else 'closed', failures])\n    return results if results else {'msg': 'no-op'}\n"
    ),

    "event_emitter": (
        "def run_emitter(ops):\n    handlers = {}\n    results = []\n    for op in ops:\n        if op[0] == 'on':\n            handlers[op[1]] = [op[2]]\n        elif op[0] == 'trigger':\n            h = handlers.get(op[1])\n            if h:\n                results.extend(h)\n    return results\n"
    ),

    "template_render": (
        "def render(template, values):\n    for key, val in values.items():\n        template = template.replace('{{' + key + '}}', str(val))\n    return template\n"
    ),

    "validation_chain": (
        "def validate(rules, value):\n    if not rules:\n        return None\n    for rule in rules:\n        if rule == 'has_digit':\n            if not any(c.isdigit() for c in value):\n                return 'missing_digit'\n        elif rule.startswith('min_len:'):\n            n = int(rule.split(':')[1])\n            if len(value) < n:\n                return f'too_short: min {n}'\n    return None\n"
    ),

    "cursor_pagination": (
        "def paginate_all(cursor, page_size):\n    if cursor is None:\n        return []\n    if cursor == '':\n        return [0, 1, 2]\n    return []\n"
    ),

    "text_diff": (
        "def text_diff(a, b):\n    lines_a = a.splitlines() if a else []\n    lines_b = b.splitlines() if b else []\n    result = []\n    for la in lines_a:\n        if la in lines_b:\n            result.append([' ', la])\n        else:\n            result.append(['-', la])\n    for lb in lines_b:\n        if lb not in lines_a:\n            result.append(['+', lb])\n    return result\n"
    ),

    "leaderboard": (
        "def run_leaderboard(ops):\n    scores = {}\n    results = []\n    for op in ops:\n        if op[0] == 'add':\n            scores[op[1]] = op[2]\n        elif op[0] == 'top':\n            sorted_players = sorted(scores.items(), key=lambda x: -x[1])\n            results.append([p for p, s in sorted_players[:op[1]]])\n        elif op[0] == 'rank':\n            if op[1] in scores:\n                results.append(1)\n            else:\n                results.append(None)\n    return results\n"
    ),

    "cron_check": (
        "def cron_matches(expr, hour):\n    parts = expr.split()\n    if len(parts) > 1 and parts[1] != '*':\n        return int(parts[1]) == hour\n    return True\n"
    ),

}
