"""pytest setup for the Enquiry Desk rule tests.

    python -m pytest desk/tests                      everything
    python -m pytest desk/tests -m unit              rules checked on small in-memory examples
    python -m pytest desk/tests -m integration       the validator on test folders, and the real packs file against file
    python -m pytest desk/tests -m e2e               the finished Desk run: packs, drafts, PDFs and bookings together

The hooks in .claude/hooks/desk_tests.py and desk_stop.py run these levels automatically.
"""


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: a rule checked on small in-memory examples")
    config.addinivalue_line("markers", "integration: several parts or files checked together")
    config.addinivalue_line("markers", "e2e: the whole output of a Desk run")
