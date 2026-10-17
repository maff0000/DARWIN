# GOLD-AUD-F mirror note (DARWIN)

**Documentation only.** This note is a pointer. It changes no code, behaviour, contract or configuration in this repository.

## What this is

An audit lane (GOLD-AUD-F, part of the GOLD MVP audit set dated 2026-10-15) examined the qualification-to-review path across CER, HSA and DARWIN. This repository was read at commit `bf1142b5be9f6988ec36b60ba3db9022c76a47af`. The canonical record lives in the GOAL repository, not here:

- Audit record: https://github.com/maff0000/GOAL/blob/main/audits/2026-10-15/gold-mvp/lanes/GOLD-AUD-F/AUDIT-F.md
- Disposition table: https://github.com/maff0000/GOAL/blob/main/audits/2026-10-15/gold-mvp/lanes/GOLD-AUD-F/DISPOSITION.md
- Lane directory: https://github.com/maff0000/GOAL/tree/main/audits/2026-10-15/gold-mvp/lanes/GOLD-AUD-F

## What the audit found about DARWIN

Recommendation recorded in the disposition table: REUSE (strategy version, specification model, fingerprinting, research contracts, APOLLO core), REFACTOR the APOLLO evaluator; not on the MVP critical path until F-04 is resolved. ATHENA and qualification modules are placeholders with nothing to disposition.

Gaps recorded against this component (identifiers refer to the audit record's section 6):

- F-02: no HSA-to-DARWIN importer and no shared fingerprint.
- F-04: the APOLLO envelope at the audited commit cannot test either reviewed candidate.
- F-05: no APOLLO_PROOF producer exists; qualification and ATHENA are placeholders.
- F-13: the relationship of any deployed DARWIN build to `main` was not verified (UNVERIFIED).

Items the audit could not check from source are marked UNVERIFIED there; they are not asserted here.

## What this note does not do

- It makes no compatibility claim between this component and any other component.
- It makes no approval claim for this component, for any strategy, or for the GOLD MVP.
- It declares no freeze of this repository or of any interface.
- It makes no statement about any production or deployed system.
- It selects or ranks no strategy. Dispositions are recommendations only; adjudication rests with the GOAL programme owners.

A further mirror note for a separate component is deferred.
