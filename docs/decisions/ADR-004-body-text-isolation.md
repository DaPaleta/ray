# ADR-004: Body text reaches the model only through a dedicated fencing tool

**Date:** 2026-08-19
**Status:** accepted

## Context

The brief states that `body_text` is attacker-controlled, and that Ray must not
follow an instruction found in email content. Six messages carry a real injection
across five patterns: a fake `system:` role marker, a memory-write demand, a tool
abuse and exfiltration demand, an injection inside a quoted reply block, and a
fake SOC clearance note.

A tool that returns a whole message row returns body text with it. Body text then
enters the context on every lookup, mixed with trusted evidence, and the model has
no marker to tell one from the other.

Most investigation steps do not need body text at all. A verdict explanation
needs the authentication results, the analyzer results, the link scan, and the
remediation. Scenario 2 is answerable in full without reading one word of the
body.

## Decision

Split message retrieval into two tools.

1. **`get_message`** returns the header fields, the authentication results, the
   attachment names, the links, and the recipient. It **excludes body text**.
2. **`get_message_body`** returns body text and nothing else. It wraps the value
   in an explicit untrusted-evidence delimiter with a fixed preamble. It also
   returns the injection findings that `injection.py` produced for that value.

`injection.py` never suppresses or edits the text. It reports. The analyst sees
the payload as inert quoted evidence, and Ray reports the attempt as a finding.

Ray treats four fields as attacker-controlled, not one: `body_text`, `subject`,
`sender_display`, and `attachment_names`. `plan.md` assumption A5 records this.
The brief names `body_text` only, but the same trust argument covers all four.

## Alternatives Considered

**One `get_message` tool that includes body text, with a prompt warning.**
Rejected. Untrusted content then enters the context on every message lookup, and
the model must apply a trust boundary that nothing in the message stream marks.

**Strip or redact suspicious spans before returning the text.** Rejected for two
reasons. The analyst needs the real payload to judge the attack, so redaction
destroys evidence. A filter also invites a bypass, and a bypassed filter is worse
than no filter because it implies a guarantee that does not hold.

**Refuse to return body text at all.** Rejected. Scenario 2 asks why a message is
malicious, and the pretext lives in the body. The analyst needs to read it.

## Consequences

**Positive.** Untrusted content enters the context only on an explicit request,
so the attack surface shrinks to the turns that actually need it. The delimiter
gives the model a real boundary to reason about. The injection finding converts a
required defence into a reported product feature, which `plan.md` section 4.5
notes is the useful result for an analyst.

**Negative.** Two tool calls instead of one when Ray does need the body. The
model may forget that a second tool exists, so the tool description and the
system prompt must state the split clearly.

**Follow-up.** Acceptance criterion 3 asserts the behaviour for all six injected
messages. A test asserts that `get_message` never returns a `body_text` value.
