"""Shared fixtures. No test in this suite calls a model (ADR-005)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ray import config as config_module  # noqa: E402
from ray import db as db_module  # noqa: E402

# Known rows, from plan.md section 2. A test asserts against these, not against a
# number retyped from memory (plan.md section 9 item 5).
MAILBOX_MSG = "93bae03bfd4b5d7bac960ab6cc8dab41"
CFO_WIRE_MSG = "276266c04c4256d0ad5b1f4f1294a2d6"
PAYSLIP_FN_1 = "d0e20c681476512bb2fd2fb32c280607"
PAYSLIP_FN_2 = "41fe8ce8b2eb51c4b286f88fc855fd14"
PHISH_DOMAIN = "login-verify.acme-portal.co"
ACME_PORTAL_CAMPAIGN = "cmp_acme_portal_2026_07"
QUAYSTONE_SENDER = "billing@quaystone-billing-portal.com"

INJECTED_MESSAGES = (
    "9d9d01fbcf305f6b860c18c2e1508359",  # fake system: maintenance mode
    "c46f1b40e71b5b0295df5950993dd34f",  # memory poisoning
    "ae0a3a1a39ea5dd08eeda8fe63cc069c",  # tool abuse and exfiltration
    "dcc290bfbc10529b9e92dcfa496ea8bc",  # injection in a quoted reply block
    "77c96d781f6b5695ab4eeccdff34a038",  # fake SOC clearance
    "38816400776a514e9346f598dfa50927",  # fabricated analyst approval
)

# The 7 flagged finance messages in the resolved window. plan.md section 2.4.
FINANCE_FLAGGED = (
    "23ae234613d553949b18ac000287ff16",
    "455ce4824e43511ca5d9b7c2be168e7b",
    "53e687d776295a019bdb76a4172cffa8",
    "2620d0afe1a35eaa93bb9e158390be16",
    "a3b5e777c16358eba499a8e02e3caaa6",
    "7562b53cecbd5b238d34b71d261f2924",
    "5978f8ed9a4c53129adaeeb21db0a7ff",
)


@pytest.fixture(scope="session")
def cfg():
    return config_module.load_config(env={})


@pytest.fixture(scope="session")
def conn(cfg) -> sqlite3.Connection:
    """The read-only query connection. Session-scoped, because it cannot mutate."""
    connection = db_module.connect_readonly(cfg.db_path)
    yield connection
    connection.close()
