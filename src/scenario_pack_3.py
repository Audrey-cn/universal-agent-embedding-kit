"""Third scenario pack: 10 additional real-world scenarios (categories 31-40).

Each scenario ships a reference solution that scores 1.0 and a *plausibly* flawed
solution that passes the obvious checks but fails a deliberately-placed boundary
check — the same discrimination discipline as packs 1 and 2. Solutions are kept as
triple-quoted source for readability; they are `exec`-compiled at evaluation time.
"""

from src.scenario_benchmark import RealScenario, ScenarioCheck

SCENARIO_PACK_3 = (
    RealScenario(
        scenario_id="to_roman",
        title="Convert an integer to a Roman numeral",
        category="integer-encoding",
        ambiguity="Standard subtractive notation (IV, IX, XL...) is assumed, 1..3999.",
        checks=(
            ScenarioCheck("correctness", "to_roman", [1], "I"),
            ScenarioCheck("correctness", "to_roman", [3], "III"),
            ScenarioCheck("correctness", "to_roman", [4], "IV"),
            ScenarioCheck("correctness", "to_roman", [9], "IX"),
            ScenarioCheck("completeness", "to_roman", [58], "LVIII"),
            ScenarioCheck("completeness", "to_roman", [40], "XL"),
            ScenarioCheck("robustness", "to_roman", [1994], "MCMXCIV"),
        ),
    ),
    RealScenario(
        scenario_id="interval_merge",
        title="Merge overlapping (and touching) intervals",
        category="interval-merge",
        ambiguity="Touching intervals ([1,3],[3,5]) are considered overlapping and merge.",
        checks=(
            ScenarioCheck("correctness", "merge", [[[1, 3], [2, 6], [8, 10]]], [[1, 6], [8, 10]]),
            ScenarioCheck("correctness", "merge", [[[1, 4], [5, 6]]], [[1, 4], [5, 6]]),
            ScenarioCheck("completeness", "merge", [[[1, 3], [3, 5]]], [[1, 5]]),
            ScenarioCheck("robustness", "merge", [[]], []),
            ScenarioCheck("robustness", "merge", [[[1, 1]]], [[1, 1]]),
        ),
    ),
    RealScenario(
        scenario_id="count_word",
        title="Count occurrences of a word, case-insensitively",
        category="text-analysis",
        ambiguity="Matching is whitespace-tokenized and case-insensitive.",
        checks=(
            ScenarioCheck("correctness", "count_word", ["a b a", "a"], 2),
            ScenarioCheck("correctness", "count_word", ["Cat cat CAT dog", "cat"], 3),
            ScenarioCheck("completeness", "count_word", ["hello world", "missing"], 0),
            ScenarioCheck("robustness", "count_word", ["", "x"], 0),
            ScenarioCheck("robustness", "count_word", ["Word word", "WORD"], 2),
        ),
    ),
    RealScenario(
        scenario_id="flatten_nested",
        title="Flatten an arbitrarily nested list",
        category="recursive-flatten",
        ambiguity="Nesting depth is unbounded; only list is treated as nestable.",
        checks=(
            ScenarioCheck("correctness", "flatten", [[1, 2, 3]], [1, 2, 3]),
            ScenarioCheck("correctness", "flatten", [[1, [2, 3]]], [1, 2, 3]),
            ScenarioCheck("completeness", "flatten", [[1, [2, [3, [4]]]]], [1, 2, 3, 4]),
            ScenarioCheck("robustness", "flatten", [[]], []),
            ScenarioCheck("robustness", "flatten", [[[], [1]]], [1]),
        ),
    ),
    RealScenario(
        scenario_id="is_balanced",
        title="Check whether brackets are balanced and correctly ordered",
        category="bracket-matching",
        ambiguity="Three bracket types; order and type must both match (no interleaving).",
        checks=(
            ScenarioCheck("correctness", "is_balanced", ["()"], True),
            ScenarioCheck("correctness", "is_balanced", ["([])"], True),
            ScenarioCheck("correctness", "is_balanced", ["([)]"], False),
            ScenarioCheck("completeness", "is_balanced", ["(()"], False),
            ScenarioCheck("robustness", "is_balanced", [""], True),
            ScenarioCheck("robustness", "is_balanced", ["]"], False),
        ),
    ),
    RealScenario(
        scenario_id="dedupe_ordered",
        title="Remove duplicates while preserving first-seen order",
        category="order-preserving-dedup",
        ambiguity="First occurrence wins; original relative order is preserved.",
        checks=(
            ScenarioCheck("correctness", "dedupe", [[1, 2, 3]], [1, 2, 3]),
            ScenarioCheck("correctness", "dedupe", [[1, 1, 2, 2, 3]], [1, 2, 3]),
            ScenarioCheck("completeness", "dedupe", [[3, 1, 3, 2, 1]], [3, 1, 2]),
            ScenarioCheck("robustness", "dedupe", [[]], []),
            ScenarioCheck("robustness", "dedupe", [[5, 5, 5]], [5]),
        ),
    ),
    RealScenario(
        scenario_id="moving_avg",
        title="Sliding-window moving average of width k",
        category="sliding-window",
        ambiguity="Only full windows count; if k > len(nums) the result is empty.",
        checks=(
            ScenarioCheck("correctness", "moving_avg", [[1, 2, 3, 4], 2], [1.5, 2.5, 3.5]),
            ScenarioCheck("correctness", "moving_avg", [[2, 4, 6], 3], [4.0]),
            ScenarioCheck("completeness", "moving_avg", [[5], 1], [5.0]),
            ScenarioCheck("robustness", "moving_avg", [[1, 2], 3], []),
            ScenarioCheck("robustness", "moving_avg", [[], 2], []),
        ),
    ),
    RealScenario(
        scenario_id="compare_versions",
        title="Compare two dotted version strings numerically",
        category="semver-compare",
        ambiguity="Components compare as integers; missing trailing components are 0.",
        checks=(
            ScenarioCheck("correctness", "compare_versions", ["1.0.0", "1.0.0"], 0),
            ScenarioCheck("correctness", "compare_versions", ["2.0.0", "1.9.9"], 1),
            ScenarioCheck("correctness", "compare_versions", ["1.0.1", "1.0.2"], -1),
            ScenarioCheck("completeness", "compare_versions", ["1.10.0", "1.9.0"], 1),
            ScenarioCheck("robustness", "compare_versions", ["1.0", "1.0.0"], 0),
        ),
    ),
    RealScenario(
        scenario_id="anagram_groups",
        title="Count how many anagram groups a word list forms",
        category="anagram-grouping",
        ambiguity="Two words are anagrams iff they share the same multiset of letters.",
        checks=(
            ScenarioCheck(
                "correctness", "num_anagram_groups",
                [["eat", "tea", "tan", "ate", "nat", "bat"]], 3
            ),
            ScenarioCheck("correctness", "num_anagram_groups", [["abc"]], 1),
            ScenarioCheck("completeness", "num_anagram_groups", [["a", "b", "c"]], 3),
            ScenarioCheck("robustness", "num_anagram_groups", [[]], 0),
            ScenarioCheck(
                "robustness", "num_anagram_groups",
                [["listen", "silent", "enlist"]], 1
            ),
        ),
    ),
    RealScenario(
        scenario_id="validate_ipv4",
        title="Validate an IPv4 address string",
        category="ipv4-validation",
        ambiguity="Exactly 4 numeric octets, each 0..255.",
        checks=(
            ScenarioCheck("correctness", "is_valid_ipv4", ["192.168.1.1"], True),
            ScenarioCheck("correctness", "is_valid_ipv4", ["0.0.0.0"], True),
            ScenarioCheck("correctness", "is_valid_ipv4", ["256.1.1.1"], False),
            ScenarioCheck("completeness", "is_valid_ipv4", ["1.1.1"], False),
            ScenarioCheck("robustness", "is_valid_ipv4", [""], False),
            ScenarioCheck("robustness", "is_valid_ipv4", ["1.2.3.4.5"], False),
            ScenarioCheck("robustness", "is_valid_ipv4", ["a.b.c.d"], False),
        ),
    ),
)

REFERENCE_PACK_3 = {
    "to_roman": '''
def to_roman(n):
    vals = [(1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'),
            (90, 'XC'), (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'),
            (5, 'V'), (4, 'IV'), (1, 'I')]
    out = ''
    for v, sym in vals:
        while n >= v:
            out += sym
            n -= v
    return out
''',
    "interval_merge": '''
def merge(intervals):
    if not intervals:
        return []
    s = sorted(intervals, key=lambda x: x[0])
    out = [list(s[0])]
    for a, b in s[1:]:
        if a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out
''',
    "count_word": '''
def count_word(text, word):
    target = word.lower()
    return sum(1 for w in text.lower().split() if w == target)
''',
    "flatten_nested": '''
def flatten(lst):
    out = []
    for x in lst:
        if isinstance(x, list):
            out.extend(flatten(x))
        else:
            out.append(x)
    return out
''',
    "is_balanced": '''
def is_balanced(s):
    pairs = {')': '(', ']': '[', '}': '{'}
    stack = []
    for c in s:
        if c in '([{':
            stack.append(c)
        elif c in pairs:
            if not stack or stack.pop() != pairs[c]:
                return False
    return not stack
''',
    "dedupe_ordered": '''
def dedupe(lst):
    seen = set()
    out = []
    for x in lst:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
''',
    "moving_avg": '''
def moving_avg(nums, k):
    if k <= 0 or k > len(nums):
        return []
    out = []
    for i in range(len(nums) - k + 1):
        window = nums[i:i + k]
        out.append(sum(window) / k)
    return out
''',
    "compare_versions": '''
def compare_versions(a, b):
    pa = [int(x) for x in a.split('.')]
    pb = [int(x) for x in b.split('.')]
    n = max(len(pa), len(pb))
    pa += [0] * (n - len(pa))
    pb += [0] * (n - len(pb))
    for x, y in zip(pa, pb):
        if x < y:
            return -1
        if x > y:
            return 1
    return 0
''',
    "anagram_groups": '''
def num_anagram_groups(words):
    groups = set()
    for w in words:
        groups.add(''.join(sorted(w)))
    return len(groups)
''',
    "validate_ipv4": '''
def is_valid_ipv4(s):
    parts = s.split('.')
    if len(parts) != 4:
        return False
    for p in parts:
        if not p.isdigit():
            return False
        if int(p) > 255:
            return False
    return True
''',
}

# Each flaw is plausible — it passes the obvious cases but fails one boundary check.
FLAWED_PACK_3 = {
    # Additive only: no subtractive pairs, so 4 -> 'IIII', 40 -> 'XXXX'.
    "to_roman": '''
def to_roman(n):
    vals = [(1000, 'M'), (500, 'D'), (100, 'C'), (50, 'L'),
            (10, 'X'), (5, 'V'), (1, 'I')]
    out = ''
    for v, sym in vals:
        while n >= v:
            out += sym
            n -= v
    return out
''',
    # Strict '<': touching intervals ([1,3],[3,5]) are not merged.
    "interval_merge": '''
def merge(intervals):
    if not intervals:
        return []
    s = sorted(intervals, key=lambda x: x[0])
    out = [list(s[0])]
    for a, b in s[1:]:
        if a < out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out
''',
    # Case-sensitive: 'Cat'/'CAT' are not counted as 'cat'.
    "count_word": '''
def count_word(text, word):
    return sum(1 for w in text.split() if w == word)
''',
    # One level deep only: [1,[2,[3]]] -> [1,2,[3]].
    "flatten_nested": '''
def flatten(lst):
    out = []
    for x in lst:
        if isinstance(x, list):
            out.extend(x)
        else:
            out.append(x)
    return out
''',
    # Counts brackets but ignores ordering: '([)]' -> True.
    "is_balanced": '''
def is_balanced(s):
    counts = {'(': 0, '[': 0, '{': 0}
    closes = {')': '(', ']': '[', '}': '{'}
    for c in s:
        if c in counts:
            counts[c] += 1
        elif c in closes:
            counts[closes[c]] -= 1
            if counts[closes[c]] < 0:
                return False
    return all(v == 0 for v in counts.values())
''',
    # set() loses first-seen order: [3,1,3,2,1] -> [1,2,3].
    "dedupe_ordered": '''
def dedupe(lst):
    return sorted(set(lst))
''',
    # Emits a partial trailing window and never guards k > len(nums).
    "moving_avg": '''
def moving_avg(nums, k):
    out = []
    for i in range(len(nums)):
        window = nums[i:i + k]
        if window:
            out.append(sum(window) / len(window))
    return out
''',
    # Lexicographic string compare: '1.10.0' < '1.9.0'.
    "compare_versions": '''
def compare_versions(a, b):
    if a == b:
        return 0
    return 1 if a > b else -1
''',
    # Groups by length, not letter multiset: distinct anagrams collapse.
    "anagram_groups": '''
def num_anagram_groups(words):
    groups = set()
    for w in words:
        groups.add(len(w))
    return len(groups)
''',
    # No octet range check: '256.1.1.1' passes.
    "validate_ipv4": '''
def is_valid_ipv4(s):
    parts = s.split('.')
    if len(parts) != 4:
        return False
    for p in parts:
        if not p.isdigit():
            return False
    return True
''',
}
