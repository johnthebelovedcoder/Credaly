The Regulatory Landscape
You're operating under two overlapping frameworks:
The Nigeria Data Protection Act (NDPA) 2023 is the primary privacy law. It replaced the NDPR and is significantly more teeth-bearing. It established the Nigeria Data Protection Commission (NDPC) as the enforcement body, requires a lawful basis for every data processing activity, mandates Data Protection Impact Assessments (DPIAs) for high-risk processing (which credit scoring is, explicitly), and requires data processor agreements with every third party you share data with.
The CBN Consumer Protection Framework and its Open Banking Regulatory Framework (2023) govern specifically how financial data flows between institutions. Any bank statement or transaction data you pull must flow through CBN-licensed API providers or direct bank partnerships with signed data sharing agreements.
These two don't conflict — they stack. NDPA governs the general privacy layer, CBN governs the financial data layer specifically. You need both.

The Consent Architecture
Think of consent as its own data system, not a feature inside your main product. It needs:
Consent Collection Layer
Every data source requires a separate, granular consent event. You cannot bundle them. "I consent to share all my data" is legally meaningless under NDPA. The user must consent to each category independently — bank data, telco data, utility data, etc. — and each consent must be time-stamped, versioned, and tied to a specific stated purpose.
The stated purpose matters legally. If you collect bank statement data "to assess creditworthiness for Lender X" you cannot then use that same consent to train your ML model or share with Lender Y. Purpose limitation is a hard rule under NDPA, not a suggestion.
Consent Token System
Each granted consent generates a token that contains: the data subject's ID, the specific data type consented to, the purpose, the third parties authorized to receive it, the expiry date, and the version of your privacy policy at time of consent. This token travels with the data through your pipeline. When a lender queries your API, the response includes a consent token reference — so they can prove to their own auditors that the data was lawfully obtained.
Consent Lifecycle Management
Consent is not permanent. NDPA gives data subjects the right to withdraw consent at any time. Your system must handle: consent granted, consent updated (user changes scope), consent withdrawn (you must stop processing and notify downstream), and consent expired (you must re-obtain before continuing). When consent is withdrawn, you need a cascade: stop ingesting new data from that source, flag existing derived features, and notify any lenders who have active scores based on that data.
Right to Explanation
Because you're doing automated credit decisioning, NDPA Section 34 gives data subjects the right to not be subject to solely automated decisions with significant effects — and if you do use automated decisioning, they have the right to request a human review and an explanation of how the decision was made. Your scoring engine needs to produce human-readable explanations alongside every score. Not just "score: 620" but "your score is primarily influenced by consistent mobile money inflows over 12 months, offset by two missed utility payments in Q3." This is also good product — it helps lenders explain rejections to applicants.

The Data Processor Agreement Layer
Every data source you tap requires a signed Data Processing Agreement (DPA) that specifies: what data is being shared, the lawful basis, the retention period, security standards, and breach notification timelines. This means separate DPAs with each telco partner, each bank or open banking provider, each utility, and each BNPL provider. It also means your lender clients sign a DPA with you — because you're sharing personal data with them as a data processor on behalf of the data subject.
Under NDPA, if you're processing data on behalf of clients, you are a data processor and they are data controllers. That distinction matters for liability.

Data Minimization and Retention
You can only hold data as long as necessary for the stated purpose. For credit scoring, this typically means raw transaction data should not be retained beyond 24 months after the last credit event. Derived features (the computed signals, not the raw transactions) can be retained longer as they are less sensitive. Your architecture should have automatic purge workflows triggered either by retention period expiry or consent withdrawal.
You also cannot pull more data than you need. If airtime top-up frequency is your signal, you don't need call records. Scope your API pulls to the minimum dataset that achieves your purpose.

The DPIA Requirement
Before you go live, NDPA requires a formal Data Protection Impact Assessment for credit scoring specifically because it qualifies as high-risk automated processing. This is a structured document that maps: what data you collect, why, the risks to data subjects, the mitigations you've put in place, and a residual risk assessment. You file this with the NDPC and it becomes part of your regulatory record. Build this early — it also becomes the backbone of your enterprise sales process, because sophisticated lenders will ask for it.

What This Becomes Commercially
Here's the counterintuitive part: a properly built consent and compliance layer is a sales asset, not just a cost center. When you walk into a tier-1 bank or a regulated insurance company, they cannot legally use your scoring API unless you can demonstrate NDPA compliance, CBN data sharing compliance, and audit-ready consent trails. Most alternative data players in Nigeria cannot do this today. The ones who can are the ones enterprise clients are allowed to work with. Your compliance architecture is your enterprise sales unlock.
It's also your moat-protector. If a competitor scrapes data or uses informal consent, they're sitting on regulatory risk. You're not. As enforcement matures — and NDPC is actively building capacity — that gap widens.