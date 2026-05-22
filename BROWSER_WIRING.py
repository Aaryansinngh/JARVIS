# Browser Agent — Wiring Guide
# How to integrate Phase 3 browser tools into your existing Phase 2 code.
# These are the only changes needed to existing files.

# ════════════════════════════════════════════════════════════
# 1. tools/builtin.py  →  add one import + one call
# ════════════════════════════════════════════════════════════

# At the bottom of load_all_tools(), add:

    from tools.browser_tools import load_browser_tools
    load_browser_tools()

# Full load_all_tools() should look like:
#
#   def load_all_tools():
#       load_builtin_tools()      # your existing line
#       from tools.browser_tools import load_browser_tools
#       load_browser_tools()


# ════════════════════════════════════════════════════════════
# 2. workflows/builtin.py  →  add browser workflows
# ════════════════════════════════════════════════════════════

# At the bottom of get_builtin_workflows(), extend the returned list:

    from workflows.browser_workflows import get_browser_workflows
    return existing_workflows + get_browser_workflows()


# ════════════════════════════════════════════════════════════
# 3. core/orchestrator_v2.py  →  extend rule router
# ════════════════════════════════════════════════════════════

# After the rule_based_route function is defined, add at module level:

    from core.browser_router import extend_rules
    rule_based_route = extend_rules(rule_based_route)

# Or, if you prefer to inline it, add this block inside rule_based_route()
# BEFORE the final "return None":

    from core.browser_router import route_browser
    from core.orchestrator_v2 import IntentType
    browser = route_browser(text)
    if browser:
        if browser.tool.startswith("workflow:"):
            return Intent(type=IntentType.WORKFLOW,
                          target=browser.tool.split(":",1)[1],
                          params=browser.params)
        return Intent(type=IntentType.TOOL,
                      target=browser.tool,
                      params=browser.params)


# ════════════════════════════════════════════════════════════
# 4. config.toml  →  optional browser settings (add to file)
# ════════════════════════════════════════════════════════════

"""
[browser]
headless          = false        # true = invisible browser (faster, no UI)
screenshots_dir   = "./data/screenshots"
timeout_ms        = 15000        # per-action timeout
default_engine    = "google"     # google | bing | duckduckgo
"""


# ════════════════════════════════════════════════════════════
# 5. Verify it works
# ════════════════════════════════════════════════════════════

# Offline test (router + registration only):
#   python test_browser_agent.py --offline

# Full test with real browser:
#   python test_browser_agent.py

# Headless full test:
#   python test_browser_agent.py --headless

# Try it in text mode:
#   python main.py --text
#   [You]: search for python internships
#   [You]: go to github.com
#   [You]: summarize this page
#   [You]: play lofi music on youtube
#   [You]: find internships for machine learning
