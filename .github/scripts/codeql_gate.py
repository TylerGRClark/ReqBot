"""Fail closed on incomplete CodeQL SARIF or error/high/critical findings.

Policy: effective result level error OR rule security-severity >= 7.0, regardless
of precision. This is a severity policy, not a claim of high-confidence detection.
"""

import argparse
import json
import math
import sys
from pathlib import Path


class InvalidSarif(ValueError):
    """Missing, malformed, or unsupported scan evidence."""


def effective_rule(result, rules):
    rule_id = result.get("ruleId")
    index = result.get("ruleIndex")
    if "rule" in result:
        raise InvalidSarif("Unsupported result.rule reference; expected CodeQL driver rules.")
    if index is not None:
        if type(index) is not int or index < 0 or index >= len(rules):
            raise InvalidSarif("Invalid ruleIndex.")
        rule = rules[index]
        if rule_id is not None and rule_id != rule["id"]:
            raise InvalidSarif("ruleId and ruleIndex disagree.")
        return rule
    matches = [rule for rule in rules if rule["id"] == rule_id]
    if len(matches) != 1:
        raise InvalidSarif("Result must resolve to exactly one rule descriptor.")
    return matches[0]


def scan_file(path):
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError, RecursionError) as err:
        raise InvalidSarif(f"Cannot read valid SARIF: {path.name}") from err
    if not isinstance(data, dict) or data.get("version") != "2.1.0":
        raise InvalidSarif("Expected SARIF version 2.1.0.")
    runs = data.get("runs")
    if not isinstance(runs, list) or not runs:
        raise InvalidSarif("No scan runs recorded.")
    blocked = []
    for run in runs:
        if not isinstance(run, dict):
            raise InvalidSarif("Invalid scan run.")
        tool = run.get("tool")
        driver = tool.get("driver") if isinstance(tool, dict) else None
        # The action's output and the documented CLI format use these two names.
        if not isinstance(driver, dict) or driver.get("name") not in (
            "CodeQL", "CodeQL command-line toolchain",
        ):
            raise InvalidSarif("Expected CodeQL driver evidence.")
        rules = driver.get("rules", [])
        if not isinstance(rules, list) or not all(
            isinstance(rule, dict) and isinstance(rule.get("id"), str) and rule["id"]
            for rule in rules
        ):
            raise InvalidSarif("Invalid rule descriptors.")
        if len({rule["id"] for rule in rules}) != len(rules):
            raise InvalidSarif("Duplicate rule descriptors.")
        invocations = run.get("invocations", [])
        if not isinstance(invocations, list):
            raise InvalidSarif("Invalid scan invocations.")
        for invocation in invocations:
            if not isinstance(invocation, dict) or invocation.get("executionSuccessful") is not True:
                raise InvalidSarif("Scan invocation did not complete successfully.")
        results = run.get("results")
        if not isinstance(results, list):
            raise InvalidSarif("Missing scan results list.")
        for result in results:
            if not isinstance(result, dict):
                raise InvalidSarif("Invalid result.")
            rule = effective_rule(result, rules)
            default = rule.get("defaultConfiguration", {})
            if not isinstance(default, dict):
                raise InvalidSarif("Invalid default rule configuration.")
            level = result.get("level", default.get("level", "warning"))
            if level not in ("none", "note", "warning", "error"):
                raise InvalidSarif("Invalid effective result level.")
            properties = rule.get("properties", {})
            if not isinstance(properties, dict):
                raise InvalidSarif("Invalid rule properties.")
            severity = properties.get("security-severity")
            if severity is not None:
                try:
                    if isinstance(severity, bool):
                        raise ValueError
                    severity = float(severity)
                except (TypeError, ValueError) as err:
                    raise InvalidSarif("Invalid security-severity.") from err
                if not math.isfinite(severity) or not 0 <= severity <= 10:
                    raise InvalidSarif("Out-of-range security-severity.")
            kind = result.get("kind", "fail")
            if kind not in ("fail", "pass", "open", "informational", "notApplicable", "review"):
                raise InvalidSarif("Invalid result kind.")
            if kind not in ("pass", "notApplicable") and (
                level == "error" or (severity is not None and severity >= 7)
            ):
                blocked.append(rule["id"])
    return blocked


def evaluate(directory):
    if not directory.is_dir():
        raise InvalidSarif("SARIF output directory is missing.")
    files = sorted(directory.glob("*.sarif"))
    if not files:
        raise InvalidSarif("No SARIF files produced.")
    return [rule for path in files for rule in scan_file(path)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        blocked = evaluate(args.directory)
    except InvalidSarif as err:
        print(f"Incomplete CodeQL evidence: {err}", file=sys.stderr)
        return 1
    if blocked:
        print(f"Blocking CodeQL findings: {sorted(set(blocked))}", file=sys.stderr)
        return 1
    print("CodeQL evidence valid; no error/high/critical findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
