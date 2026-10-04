> **Provenance and caveat.** These labels are one reviewer's judgment (Claude, 2026-10-04) and have
> **not** been independently audited. The sample is 60 of 1,845 survivors (seed 2026,
> `eval/wp_44_2_audit.py`), so the percentages carry wide uncertainty (pure junk 5/60 = 8%,
> roughly 3-18% at 95% confidence). Treat as a pointer for Phase 45's labeled gold set, not a result.
> Labels are keyed by quote text so they stay valid if ordering changes.

# WP-44.2 Step 1 -- hand labels of surviving requirements (Claude's judgment; please audit)

Labels: REAL = states an obligation/recommendation a reader could act on; FRAGMENT = a clause piece that is not a standalone requirement (list tail, gerund phrase, bare noun item); JUNK = not a requirement (glossary preamble, acknowledgement text, pure fact, cross-reference); BORDERLINE = descriptive or permissive statement.

## A. Random sample of 60 of the 1,845 survivors (seed 2026)

Counts: BORDERLINE(descriptive/permissive) 6, REAL 46, FRAGMENT 3, JUNK 5

 1. BORDERLINE(descriptive/permissive) [DODI 5200.44 c33] (1)  In coordination with the Director, National Security Agency, may independently conduct operational and technical observations and assessments in support of the use of the authority in Section 325
 2. REAL                               [DODI 8551.01 c24] The PPSM CCB evaluates nonstandard usage implementation requests for availability and interoperability to support operational needs.
 3. REAL                               [afi10-2402 c92] The HAF CARM Program will collaborate with HAF/A4 MA office to provide AF submissions to the JS assessment data call.
 4. REAL                               [afi10-2402 c99] MAJCOM/DRUs and FOAs (as appropriate) will identify funding requirements to implement risk response actions through the PPBE process and inform the HAF CARM Program of any unfunded risk reduction requ
 5. REAL                               [afi17-203 c37] Preliminary response actions should not result in a self-imposed denial of service;
 6. FRAGMENT                           [dafman17-1305 c65] and 4)  continuous  professional  development  of  a  minimum  of  20  hours  per  year (or vendor certification maintenance minimums, whichever is greater).
 7. REAL                               [DODI 5200.44 c23] Supports DoD Components with assessment of software analysis tools and practices and provides guidance on software and hardware vulnerability reduction and malicious intent identification to enable ac
 8. REAL                               [dafman17-1305 c88] Privileged access shall be removed for any personnel who does not have or maintain qualifications in active and good standing after the transition date.
 9. JUNK                               [DODI 5200.48 c87] Unless otherwise noted, these terms and their definitions are for the purpose of this issuance.
10. JUNK                               [dafman17-1305 c102] Upon being assigned, I am or may be expected to perform all or some of the cybersecurity tasks as defined in DAFMAN 17-1305, my Position Description or other applicable documents.
11. REAL                               [afi13-550 c60] Execute authorizing official duties for a subset of AF NC3 systems IAW DoDI 8510.01, AFI 17-130, and applicable CDRUSSTRATCOM Memoranda delegating authorizing official responsibilities for specified s
12. BORDERLINE(descriptive/permissive) [afi17-203 c10] Tier One provides DoD-wide DCO and DoDIN Operations operational direction and support to all Combatant Commanders, Services and Agencies (C/S/As).
13. REAL                               [afi13-550 c28] All MAJCOMs, the Air National Guard (ANG), Field Operating Agencies (FOAs) and Direct Reporting Units (DRUs), and their subordinate units will support Air Force NC3 systems, equipment, personnel, and 
14. REAL                               [afi10-2402 c33] Oversee and maintain overall responsibility for implementing a CARM program for the purpose of managing risk to AF TCAs.
15. REAL                               [dafman17-1305 c18] The DAF Chief Information Officer (SAF/CN) shall: Coordinate with AF/A2/6 and SF/COO on updates to the Enlisted and Officer Classification Directories to reflect SEI requirements and updates to the ci
16. REAL                               [afi13-550 c39] Identify AF NC3-related facility requirements at ACC installations (e.g. command centers, wing command posts), to include EMP protection, sustainment, and maintenance, and coordinate mitigation resour
17. REAL                               [afi13-550 c21] develop and establish Air Force nuclear surety standards and policies for safety, and will assess nuclear weapons systems and systems requirements for safety.
18. REAL                               [dafman17-1305 c53] Supervisors shall: Incorporate cyberspace qualification requirements in accordance with Chapters 3 and 4 of this document within the master training plan and training documentation for the cyberspace 
19. BORDERLINE(descriptive/permissive) [afman17-2101 c52] Coordination and information sharing with civil First Responders in an accessible information environment is necessary to protect and defend tenants onboard, and directly adjacent, to DoD Installation
20. REAL                               [dafman17-1305 c12] Users will refresh their training within 365 calendar days when newer versions of the training becomes available.
21. REAL                               [afpd_17-1 c23] Participate in the cyberspace governance forums, as required.
22. BORDERLINE(descriptive/permissive) [afi10-2402 c81] The CARM Program utilizes products from three separate assessments to determine risk to AF TCAs and develop risk management strategies.
23. REAL                               [afpd_17-1 c13] Be responsible for AF Joint Capabilities Integration and Development System planning and requirements development processes and procedures for cyberspace capabilities.
24. REAL                               [dafman17-1305 c5] all supplements must be routed to the OPR of this publication for coordination prior to certification and approval.
25. REAL                               [afi13-550 c50] Provide NC3 architecture integration and planning support to improve design integrity, survivability, endurability, interoperability, compatibility, security, performance, and reliability as component
26. REAL                               [afi10-2402 c48] Establish POCs in Functional and Special Staff Directorates, as required, to socialize and advance CARM priorities; plus any System Program Office (SPO) / Program Management Office (PMO) program POCs 
27. REAL                               [DODI 8410.03 c10] Establish and maintain definitions and interface control documents for standard mechanisms for exchanging NM information between NM systems and for exposing data to nonNM systems.
28. REAL                               [CJCSI 6510.02G c5] Cryptographic product modernization planning and/or execution must ensure product removal from mission areas within 10 years of the date listed in the LYOU table in reference (b).
29. REAL                               [afi13-550 c68] Establish and maintain an AN/USQ-225 operational reporting process IAW AFMAN 10-206, Operational Reporting, to identify, elevate, and resolve system problems.
30. REAL                               [DODI 5200.44 c5] All-source intelligence analysis of suppliers of critical components will be used with supply chain illumination capabilities as part of supplier due diligence to inform risk management decisions.
31. FRAGMENT                           [DODI 5200.44 c29] Using software assurance and hardware assurance tools and practices available through the JFAC, as appropriate.
32. REAL                               [DODI 8410.03 c34] NM SLAs and other agreements shall be structured to complement or extend other SLAs entered into by DoD Components.
33. REAL                               [dafman17-1305 c38] Provide coordination to a Servicing Classification Office not located within AFPC, that  inherits  or  assumes  functions  described  by paragraph  2.12 of  this  manual  where appropriate.
34. REAL                               [DODI 5200.44 c19] Provides congressional notifications, as required, of exclusion determinations that are made by the USD(A&S) in accordance with Section 3252 of Title 10, U.S.C..
35. REAL                               [afi10-2402 c52] Coordinate remediation and mitigation requests to systems, systems of systems, and their supply-chain and life cycle management with a system's PMO, SPO, and other organizations as needed.
36. REAL                               [CJCSI 6510.02G c15] Address capability requirements for modernized, cryptographic cybersecurity solutions for C4ISR, IT, and weapons systems developments that are intended to replace operational systems that employ at-ri
37. REAL                               [dafman17-1305 c37] update the appropriate AF Enlisted Classification Directory (AFECD) or AF Officer Classification Directory (AFOCD) with SEIs to track the military cybersecurity workforce roles and proficiency levels.
38. REAL                               [dafman17-1305 c94] The AO, PMO, or unit must use appropriate contracting methods.
39. REAL                               [afman17-2101 c19] Manages the Consolidated MAJCOM Circuit Management Office (CMO) for all MAJCOMs and executes the consolidated MAJCOM CMO duties as identified in Chapter 2, paragraph 2.8.2.
40. JUNK                               [afi10-2402 c80] The system is designed to serve as a common entry point  for  the  MAJCOM/DRUs  and  FOAs  (as  appropriate)  and  is  one-way  web  shared with CCMDs, JS/J33, and ASD (HD&GS) databases and representa
41. REAL                               [afman17-2101 c16] Coordinates  with  SAF/CIO  A6  and  the  Deputy  Under  Secretary  of  Air  Force, Management (SAF/MG) to develop  and  publish  guidance  and  processes  to  ensure  the bandwidth efficiency of syst
42. REAL                               [DODI 8551.01 c20] (3) Boundary protection devices will block PPS not implemented in accordance with DoD PPSM standards.
43. REAL                               [DODI 5200.48 c78] The originator or other competent authority (e.g., initial FOIA denial and appellate authorities) will terminate the CUI status of specific information when the information no longer requires protecti
44. BORDERLINE(descriptive/permissive) [afi10-2402 c4] The annual schedule of AFMAAs are developed by AFSFC in coordination with AF/A3OA with primary consideration of the assessment requirements dictated by AF Mission Assurance and Antiterrorism programs.
45. REAL                               [DODI 8410.03 c18] Ensure that NM systems are resilient to manmade or natural events that may cause failure, loss or disruption of NM capabilities.
46. REAL                               [NIST.SP.800-125 c58] Therefore, organizations should minimize the creation, storage, and use of unnecessary images.
47. JUNK                               [NIST.SP.800-125 c69] Most bare metal hypervisors have access controls to the system.
48. REAL                               [dafman17-1305 c30] Report the status of their cyberspace workforce metrics to SAF/CN at the close of each fiscal year or as directed.
49. REAL                               [NIST.SP.800-125 c87] In cases where the legacy application must be provided full network access, care must be taken to ensure that the data it receives is not malicious
50. REAL                               [afpd_17-1 c10] Oversee, establish, integrate and maintain the target baseline (TB) and implementation baseline (IB) in coordination with appropriate governance forums.
51. REAL                               [afi10-2402 c100] MAJCOM/DRUs and FOAs (as appropriate) will maintain current and accurate records of identified TCAs and risk remediation efforts in the AF CARM system of record.
52. JUNK                               [afi17-203 c30] Refer to paragraph 4 for guidance on identifying exercise incidents/events reported, and the processes for de-conflicting real world and exercise activities.
53. REAL                               [DODI 5200.44 c2] The United States Coast Guard will adhere to DoD cybersecurity requirements, standards, and policies in this issuance in accordance with the direction in Paragraphs 4.(a) through 4.(d) of the January 
54. REAL                               [afman17-2101 c46] Ensure unit's under their purview reconcile their monthly LHC invoices for telecommunications equipment and service inventories, CSA's, and/or other acquisition documents before authorizing payment.
55. BORDERLINE(descriptive/permissive) [NIST.SP.800-125 c49] The hypervisor is responsible for managing guest OS access to hardware (e.g., CPU, memory, storage).
56. REAL                               [DODI 5200.44 c10] establishes processes and procedures to ensure assured access to trusted microelectronics pursuant to Section 231 of Public Law 114-328
57. REAL                               [afi13-550 c28] Support AF NC3 requirements development, metric development, metric updating, and program management reviews.
58. REAL                               [afi13-550 c8] Provide guidance and direction to manage the AF NC3 architecture and manage the AN/USQ-225 configuration baseline.
59. REAL                               [DODI 8410.03 c37] NM system users shall comply with the applicable cybersecurity training and certification requirements IAW Reference (ad).
60. FRAGMENT                           [DODI 8410.03 c34] (1) Network latency and packet loss on per-hop and end-to-end basis by traffic type.

## B. All 24 survivors under 40 characters

Counts: REAL 10, FRAGMENT 13, BORDERLINE(descriptive/permissive) 1

 1. REAL                               [CJCSI 6510.02G c29] KERs shall be approved by the MC4EB.   (header: CRYPTOGRAPHIC MODERNIZATION PLANNING PROCESS FOR REQUESTING )
 2. FRAGMENT                           [DODI 5200.01 c2] (3) Restrain competition.   (header: 3.  POLICY.  It is DoD policy that:)
 3. FRAGMENT                           [DODI 5200.01 c9] Maintains Reference (n).   (header: 1.  UNDER SECRETARY OF DEFENSE FOR INTELLIGENCE AND SECURITY)
 4. FRAGMENT                           [DODI 5200.48 c15] in coordination with USD(I&S)   (header: 2.8.  USD(R&E).)
 5. FRAGMENT                           [DODI 5200.48 c57] satisfy the CUI requirements   (header: 3.7.  GENERAL DOD CUI REQUIREMENTS.)
 6. FRAGMENT                           [DODI 8410.03 c33] Required NM data update rates.   (header: 4.  SLAs)
 7. FRAGMENT                           [DODI 8410.03 c33] Location of the NM event.   (header: 4.  SLAs)
 8. FRAGMENT                           [NIST.SP.800-125 c8] implement the following recommendations   (header: Executive Summary)
 9. FRAGMENT                           [NIST.SP.800-125 c42] enforce security requirements   (header: 2.4.1.2 Multiple Server Virtualization)
10. FRAGMENT                           [NIST.SP.800-125 c90] developing virtualization policy   (header: 5. Secure Virtualization Planning and Deployment)
11. REAL                               [afi10-2402 c59] Participate in the CARM WG as required.   (header: 2.19. Air Force Components to the Combatant Commands.)
12. REAL                               [afi10-2402 c67] Support MAAs of TCAs.   (header: 2.20. FOAs.)
13. REAL                               [afi10-2402 c124] Identify COAs for each of these risks.   (header: V. Bisk Assessment Summary)
14. REAL                               [afi10-2402 c127] Have load-shedding plan   (header: VI. Risk Response)
15. REAL                               [afi10-2402 c127] Have portable equip. avail.   (header: VI. Risk Response)
16. REAL                               [afi10-2402 c127] Update barrier plan for higher FPCONs   (header: VI. Risk Response)
17. REAL                               [afi13-550 c21] Act as AF lead for AF NC3 requirements.   (header: 2.2.4. Deputy Chief of Staff for Operations ( AF/A3 ) will:)
18. REAL                               [afi13-550 c34] AFNWC/NC will co-chair the Group.   (header: 3.3. Responsibilities.)
19. FRAGMENT                           [afi17-203 c32] then take the indicated Actions   (header: 3.3.1. Objectives.)
20. FRAGMENT                           [afi17-203 c32] and the Primary Recipient will be   (header: 3.3.1. Objectives.)
21. FRAGMENT                           [afi17-203 c32] and Informational Recipients will be   (header: 3.3.1. Objectives.)
22. BORDERLINE(descriptive/permissive) [afman17-2101 c18] Serves as the AF LAFO   (header: 2.3. AF  Long  Haul  Communications  Flight,  38th  Cyberspa)
23. REAL                               [afman17-2101 c22] Manage AF LHC Program Element 33126F.   (header: 2.3. AF  Long  Haul  Communications  Flight,  38th  Cyberspa)
24. FRAGMENT                           [afman17-2101 c25] shall be coordinated with the customer   (header: 2.3. AF  Long  Haul  Communications  Flight,  38th  Cyberspa)
