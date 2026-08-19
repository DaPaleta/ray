# Capability 4 — organizational memory, stored then applied on a later turn

---



---

# Our CFO is Rachel Adler and she never sends wire requests over email. Remember that.

*Model: `claude-haiku-4-5-20251001` · 2026-08-19T12:43:51Z*

## Answer

I propose to remember: **Rachel Adler, the CFO, never sends wire requests over email.**

This will be a durable policy that applies to any wire request emails claiming to come from her. Please confirm, and I'll store it.

## How Ray reached it

**1. `remember`**
   - arguments: `kind='policy', content='Rachel Adler, the CFO, never sends wire requests over email.'`

   ```
   MEMORY PROPOSAL — awaiting the analyst's confirmation. Nothing is stored yet.
     proposal_id: mem_83f5536799a13ea7
     kind:        policy (A general rule about how the organization behaves, naming no single indicator to sweep for — for example that a named executive never emails wire requests. Choose this only when there is no indicator to watch.)
     content:     Rachel Adler, the CFO, never sends wire requests over email.
     rationale:   This is a durable fact about executive communication practices that should inform verdict decisions on any wire request emails claiming to come from the CFO.
   Tell the analyst what you propose to remember and ask them to confirm it. Do NOT cite this proposal_id as [mem:...] — no row exists until the analyst confirms, so citing it now fails the grounding check. Quote the proposed content in plain words instead.
   ```

## Grounding check

- citations checked: 0
- every citation resolves to a real row: **True**

## Memory proposed this turn

- `policy`: Rachel Adler, the CFO, never sends wire requests over email. (awaiting the analyst's confirmation)


---

# Now apply that policy. Has anything in the last two weeks claimed to be a wire request from Rachel Adler? Check the recorded verdict and tell me whether you agree with it.

*Model: `claude-haiku-4-5-20251001` · 2026-08-19T12:43:54Z*

## Answer

**I disagree with the recorded verdict. This message should not be safe.**

**The finding:** Message [msg:276266c0] claims to be a wire request from Rachel Adler, the CFO, sent on 2026-08-13. The recorded verdict is [decision:276266c0] safe with no attack type.

**Why the verdict is wrong:**

1. **The policy you just confirmed applies directly.** Rachel Adler never sends wire requests over email. This message is a wire request. It therefore cannot be legitimate, regardless of what the analyzers found.

2. **The sender domain is a lookalike, not the real CFO domain.** The message came from `rachel.adler@acme-robotics.com` [msg:276266c0], not `rachel.adler@acme.com`. The domain `acme-robotics.com` is a lookalike that resembles the organization's primary domain `acme.com` but is not it. While SPF, DKIM, and DMARC all pass on `acme-robotics.com`, that only proves the attacker owns and configured that lookalike domain correctly — it does not prove the sender is Rachel Adler.

3. **The stage2 analyzer made a critical error.** It treated this as "internal correspondence" because "display name matches a known executive" and authentication passed [analyzer:276266c0/stage2]. But authentication on a lookalike domain does not establish identity. The analyzer should have flagged the domain mismatch.

4. **The NLP analyzer correctly identified the threat pattern.** It scored this as malicious (0.59) [analyzer:276266c0/nlp-analyzer], noting "Executive-to-finance payment request with secrecy and time pressure" — exactly the pattern of a fake-CFO wire request.

**The message is still in the inbox** [remediation:276266c0] with no action taken. It reached Gwen Mercer in finance [msg:276266c0], who is exactly the person an attacker would target for a wire request.

**Recommendation:** This should be quarantined immediately. It is a credential phishing / fake-CFO wire request attack, not a safe message.

## How Ray reached it

**1. `find_messages`**
   - arguments: `sender_email='rachel.adler@acme.com', subject_contains='wire', relative_window='last two weeks', limit=50`
   - window: the whole recorded window, up to the newest row 2026-08-16T17:10:57Z

   ```
   Found 0 message(s) matching the filters.
   
   (no rows)
   ```

**2. `find_messages`**
   - arguments: `subject_contains='wire', relative_window='last two weeks', limit=50`
   - window: the whole recorded window, up to the newest row 2026-08-16T17:10:57Z
   - rows cited: [msg:276266c0]

   ```
   Found 1 message(s) matching the filters.
   
   id       | received_at          | sender_email                   | subject                             | recipient   | department | verdict | attack_type | remediation                   
   ---------|----------------------|--------------------------------|-------------------------------------|-------------|------------|---------|-------------|-------------------------------
   276266c0 | 2026-08-13T03:00:00Z | rachel.adler@acme-robotics.com | Wire — confidential, time sensitive | Gwen Mercer | finance    | safe    | (none)      | no action taken (in the inbox)
   ```

**3. `get_message`**
   - arguments: `message_id='276266c0'`
   - rows cited: [msg:276266c0] [user:u_ap]

   ```
   Message 276266c0 [msg:276266c0]
   Subject: Wire — confidential, time sensitive
   Received: 2026-08-13T03:00:00Z
   From: Rachel Adler <rachel.adler@acme-robotics.com>
   To: Gwen Mercer (finance) [user:u_ap]
   Authentication — SPF: pass, DKIM: pass, DMARC: pass
   Attachments: []
   Campaign id: (none)
   
   Links (0):
   (no rows)
   ```

**4. `get_detection`**
   - arguments: `message_id='276266c0'`
   - rows cited: [msg:276266c0] [analyzer:276266c0/nlp-analyzer] [analyzer:276266c0/sender-reputation] [analyzer:276266c0/stage2] [decision:276266c0] [remediation:276266c0]

   ```
   Evidence bundle for message 276266c0 [msg:276266c0]
   
   Analyzers that ran (3 of 4):
   analyzer          | verdict   | score | reasoning                                                                                                                                         
   ------------------|-----------|-------|---------------------------------------------------------------------------------------------------------------------------------------------------
   nlp-analyzer      | malicious | 0.59  | Executive-to-finance payment request with secrecy and time pressure; no links or attachments to corroborate.                                      
   sender-reputation | benign    | 0.31  | Sender domain authenticates cleanly (SPF, DKIM, DMARC all pass). No prior reputation signals.                                                     
   stage2            | benign    | 0.22  | Full authentication pass and display name matches a known executive. No malicious URLs or attachments present; treated as internal correspondence.
   
   Analyzers that did NOT run (unknown, not benign — IR10): link-scanner
   
   Decision: verdict=safe, attack_type=(none), decided_at=2026-08-13T03:01:00Z [decision:276266c0]
   
   Remediation: action=none (no action taken (in the inbox)), actioned_at=2026-08-13T03:01:00Z, actioned_by=auto [remediation:276266c0]
   ```

**5. `domain_intel`**
   - arguments: `domain='acme-robotics.com'`
   - rows cited: [msg:276266c0] [decision:276266c0] [remediation:276266c0]

   ```
   Domain intel for acme-robotics.com:
   - As a link domain: no rows.
   - As a sender domain: 1 messages.
       spf=pass dkim=pass dmarc=pass: 1
   - First appearance: 2026-08-13T03:00:00Z. Last appearance: 2026-08-13T03:00:00Z.
   - Recipients reached: 1 distinct users across 1 departments (finance).
       No VIP recipient was reached.
       No message on this domain carries a campaign_id.
   - Decision verdict spread: safe: 1
   - Remediation state: none: 1
   - LOOKALIKE WARNING: acme-robotics.com resembles the organization's primary domain acme.com but is NOT it. A passing SPF/DKIM/DMARC result on this domain is not reassurance — it only proves the attacker's own domain is configured correctly, not that the sender is who it claims to be.
   ```

## Grounding check

- citations checked: 7
- every citation resolves to a real row: **True**
- the first answer failed this check, so Ray was asked once to re-cite from the tool output it already had

