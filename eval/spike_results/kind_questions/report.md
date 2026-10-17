# Kind-aware draft audit questions, round 5: report for Tyler

Plain words. Nothing in the live checklist or index was touched. Earlier reports are kept: `report_round1.md`, `report_round3.md`, `report_round4.md`. **I do not grade questions.** The seven documents used in round 4 are no longer a clean test (their rows drove these fixes); the fresh document below is the only clean test left, and it was run once with the rules frozen first.

## The short version

- **Today's questions are no longer deleted.** The new rule can only add a question where a row has none, or replace today's question when the new one clearly carries the stated limit and today's does not. The only removals allowed are a bare "Can X ...?" question or an invented "consent / recognize" question; each is listed.
- **Seven documents (regression):** 1181 rows, 0 dropped; 35 model calls in total. Rows whose question changed: 8 added or replaced, 2 removed (both are "consent" questions in DODI 5200.48 3.10), 2 pointer suppressions, 68 "recommended" labels.
- **The three missed limits the reviewer named** now get a question (listed below). They were tuned for, so they are regression cases and not evidence the rules generalise.
- **Fresh document dafi36-2903** (2132 rows, 331 classed as permission): 92 gate-passing permission rows were asked of the model; the other 218 were not asked (call budget) and keep today's question. 18 questions added, 0 replaced, 0 left at today's, 0 removed, 17 "recommended" labels, 15 pointer suppressions.
- **Mechanical checks:** among accepted new questions, 0 drop a number or qualifier, 0 turn a "may" into a happened-fact, 0 start with a bare "this/it". The checks rejected 3 of 19 model questions on the seven documents and 13 of 31 on the fresh one.

## The fixes, in plain words

1. **Additive only** (above).
2. **"Such as" and "such cases" are no longer treated as a missing reference** unless "such" opens the question.
3. **The rule only fires when may/can is the main verb of the sentence.** Test used: take the sentence holding the may/can; drop an opening "When ...," clause; look only at what follows the last colon or semicolon; the words before the may/can must contain no "that/which/if/when/unless/because", no "shall/must/will/should/need to/ensure", no "No ..."/"unless"/"may not", must not start with a command verb (a role bullet like "Administers ..."), and be 25 words or fewer; and the words after must not be "include / vary / need / contain / require". Rows that fail keep today's question and the model is not even asked.
4. **A new question may not ask whether the permitted act happened** ("may be used" turned into "was used"). Mechanical: a verb that follows the source's may/can may not appear only in the asked half of the question.
5. **Guidance documents are left alone.** Test: permission + recommendation rows are at least 25% of the document's rows. This excludes NIST.SP.800-125 (38%). Every other document is under 8%; dafi36-2903 is 16% so it is not excluded. For an excluded document today's questions stay and the "recommended" labels still apply.

## Which documents the gate excludes

| Document | Rows | Permission + recommendation share | Permission path |
|---|---|---|---|
| CJCSI 6510.02G | 118 | 4% | ON |
| DODI 5200.01 | 75 | 1% | ON |
| DODI 5200.44 | 107 | 4% | ON |
| DODI 5200.48 | 295 | 8% | ON |
| DODI 8410.03 | 177 | 3% | ON |
| DODI 8551.01 | 86 | 2% | ON |
| NIST.SP.800-125 | 323 | 38% | OFF (guidance prose) |
| dafi36-2903 | 2132 | 16% | ON |

## Seven documents (regression; no longer a clean test)

| Document | Rows | Permission rows | Stopped by the main-verb gate | Asked | Added | Replaced | Today's kept | Removed | Pointers suppressed | Labels |
|---|---|---|---|---|---|---|---|---|---|---|
| CJCSI 6510.02G | 118 | 3 | 0 | 3 | 0 | 0 | 1 | 0 | 0 | 2 |
| DODI 5200.01 | 75 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| DODI 5200.44 | 107 | 4 | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 0 |
| DODI 5200.48 | 295 | 20 | 4 | 16 | 3 | 2 | 9 | 2 | 1 | 3 |
| DODI 8410.03 | 177 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 5 |
| DODI 8551.01 | 86 | 2 | 0 | 2 | 1 | 0 | 1 | 0 | 0 | 0 |
| NIST.SP.800-125 | 323 | 65 | 65 | 0 | 0 | 0 | 0 | 0 | 0 | 58 |

### Every permission row whose question changed from today's (seven documents)

| Row | Source text | Today's question | New question | What happened |
|---|---|---|---|---|
| DODI 5200.44 2.10 (inferred) | In addition to the responsibilities in Paragraph 2.9., the Secretaries of the Military Departments: In accordance with Section 3252(c) of T... | (none) | When the Secretaries of the Military Departments delegate this responsibility no lower than the service acquisition executive for the department concerned, is it in accordance with Section 3252(c) of Title 10, U.S.C. and DFARS Part 239.7303(b)? | added: new boundary question where today's row has none |
| DODI 5200.44 2.11 (inferred) | Takes all necessary and appropriate actions to secure, defend, and operate the DOD information network in accordance with existing authorit... | (none) | When the Commander, USCYBERCOM conducts operational and technical observations and assessments in support of the use of the authority in Section 3252 of Title 10, U.S.C., is it done in coordination with the Director, National Security Agency? | added: new boundary question where today's row has none |
| DODI 5200.48 3.10 (inferred) | By using this IS (which includes any device attached to this IS), you consent to the following conditions: -At any time, the USG may inspec... | Does the unit consent to allowing the USG to inspect and seize data stored on this IS at any time? | (no question) | removed_capability: no stated limit; today's question was only a capability / invented question (removed) |
| DODI 5200.48 3.10 (inferred) | By using this IS (which includes any device attached to this IS), you consent to the following conditions: -Communications using, or data s... | Do users consent to the fact that communications using, or data stored on, this IS are not private and may be subject to routine monitoring, interception, and search for any USG-authorized purpose when they use this IS? | (no question) | removed_capability: no stated limit; today's question was only a capability / invented question (removed) |
| DODI 5200.48 3.4 (inferred) | DoD operational CUI (not related to intelligence) may be marked as REL TO. | (none) | When DoD operational CUI (not related to intelligence) is marked as REL TO, is it done when warranted and consistent with relevant law, regulation, or government-wide policy or DoD policy? | added: new boundary question where today's row has none |
| DODI 5200.48 3.7 (inferred) | Some significant points about DoD CUI include: DoD CUI may be disseminated to DoD personnel to conduct official DoD and U.S. Government bus... | (none) | When DoD CUI is disseminated to DoD personnel to conduct official DoD and U.S. Government business, is it done in accordance with a law, regulation, or government-wide policy? | added: new boundary question where today's row has none |
| DODI 5200.48 3.9 (inferred) | CUI not controlled as NOFORN may be released or disclosed to non-U.S. citizens employed by the DoD if: Access to such information would hel... | Does the unit avoid releasing or disclosing CUI not controlled as NOFORN to non-U.S. citizens employed by the DoD when access would be detrimental to the interests of the DoD or the U.S. Government? | When CUI not controlled as NOFORN is released or disclosed to non-U.S. citizens employed by the DoD, does access to such information help accomplish a lawful and authorized DoD mission or purpose and would it not be detrimental to the interests of the DoD or the U.S. Government? | replaced: replaced today's question: new question carries 100% of the limit's words, today's 45% |
| DODI 5200.48 4.1 (inferred) | CUI information and material may be transmitted via first class mail, parcel post, or, bulk shipments. | (none) | When CUI information and material are transmitted via first class mail, parcel post, or, bulk shipments, is the transmission done only by one of those means? | added: new boundary question where today's row has none |
| DODI 5200.48 4.5 (inferred) | Record and non-record CUI documents may be destroyed by means approved for destroying classified information or by any other means making i... | Are record and non-record CUI documents being destroyed by means that make them unreadable, indecipherable, and unrecoverable? | When record and non-record CUI documents are destroyed by means approved for destroying classified information or by any other means making it unreadable, indecipherable, and unrecoverable the original information such as those identified in NIST SP 800-88, is the destruction in accordance with Sec... | replaced: replaced today's question: new question carries 100% of the limit's words, today's 0% |
| DODI 8551.01 2.4 (inferred) | The DoD Component heads: A representative from OIG DoD may attend in a non-voting role only. | (none) | When A representative from OIG DoD attends, is it done in a non-voting role only? | added: new boundary question where today's row has none |

### The reviewer's three missed-limit cases (regression cases, tuned for)

| Row | Source text | Today's question | New question | What happened |
|---|---|---|---|---|
| DODI 5200.48 4.1 (inferred) | CUI information and material may be transmitted via first class mail, parcel post, or, bulk shipments. | (none) | When CUI information and material are transmitted via first class mail, parcel post, or, bulk shipments, is the transmission done only by one of those means? | added: new boundary question where today's row has none |
| DODI 5200.48 3.7 (inferred) | Some significant points about DoD CUI include: DoD CUI may be disseminated to DoD personnel to conduct official DoD and U.S. Government bus... | (none) | When DoD CUI is disseminated to DoD personnel to conduct official DoD and U.S. Government business, is it done in accordance with a law, regulation, or government-wide policy? | added: new boundary question where today's row has none |
| DODI 8551.01 2.4 (inferred) | The DoD Component heads: A representative from OIG DoD may attend in a non-voting role only. | (none) | When A representative from OIG DoD attends, is it done in a non-voting role only? | added: new boundary question where today's row has none |

### Rows where the permission path found nothing and today's question stays, or there was none

Seven documents: 11 rows keep today's question after the model's question was rejected or not clearly better; 3 rows have no question before and none after. The complete row list is in `outputs/round5_regress_rows.json`.

### Pointer suppressions (read by hand, as before)

- DODI 5200.48 (no number): "Referenced definitions related to CUI in Section 2002.4 of Title 32, CFR can be found at https://intelshare.intelink.go..." (today's question: none). No duty.
- DODI 8410.03 (no number): "This instruction is available on the Directives Division Website at https://www.esd.whs.mil/DD/." (today's question: Is this instruction available on the Directives Division Website at https://www.esd.whs.m...). No duty.

## Fresh document: dafi36-2903 (the clean test, run once with the rules frozen)

Rows processed: permission, recommendation and pointer rows only (363 of 2132). Permission rows: 331; stopped by the main-verb gate: 21; asked: 92 (fixed order by SHA-1 of the row id, because the call budget did not cover every gate-passing row); not asked: 218. Model calls this round (cumulative): 132.

### Every permission row whose question changed from today's (fresh document)

| Row | Source text | Today's question | New question | What happened |
|---|---|---|---|---|
| dafi36-2903 (no number) | The morale T-Shirt may also display the organizational emblem on the back of the undershirt in a larger diameter as authorized by commander... | (none) | When an organizational emblem is displayed on the back of the morale T-shirt in a larger diameter, was it authorized by commanders? | added: new boundary question where today's row has none |
| dafi36-2903 (no number) | Wing or squadron commanders may approve display of organizational emblems, as officially and currently approved, not to exceed 5-inches in ... | (none) | When wing or squadron commanders approve the display of organizational emblems on morale undershirts as officially and currently approved, not to exceed 5-inches in diameter, in cloth or silk screen, are these conditions met? | added: new boundary question where today's row has none |
| dafi36-2903 1.2.8 | Officers may wear the rank insignia of the next higher rank if frocked to that rank. | (none) | When an officer wears the rank insignia of the next higher rank, if frocked to that rank, was the officer frocked to that rank? | added: new boundary question where today's row has none |
| dafi36-2903 10.7.1.1 | Campaign (Air Commando) hat, with one edge rolled, may only be worn while at heritage events with a specified time and place designated by ... | (none) | When Special Operations Units wear the Campaign (Air Commando) hat, with one edge rolled, is it worn only while at heritage events with a specified time and place designated by the commander? | added: new boundary question where today's row has none |
| dafi36-2903 10.7.12 | Commanders of Airmen in these AFSCs may authorize wear of dark blue shorts in lieu of the Operational Camouflage Pattern (OCP) trousers in ... | (none) | When Commanders of Airmen in these AFSCs authorize wear of dark blue shorts in lieu of OCP trousers in industrial areas, such as the flight line, hangars, warehouses, or dock areas outside of climate-controlled environments and when the ambient high temperature is forecast to meet or exceed 80 degr... | added: new boundary question where today's row has none |
| dafi36-2903 3.1.3 | One or two braids or a single ponytail or equivalent may be worn down the member's back with length not extending below a horizontal line r... | (none) | When a member wears one or two braids or a single ponytail or equivalent down the back, does the length not extend below a horizontal line running between the top of each sleeve inseam at the under arm through the shoulder blades? | added: new boundary question where today's row has none |
| dafi36-2903 5.1.1 | When sleeves are not rolled up, cuffs may remain visible or be folded inward twice. | (none) | When cuffs remain visible or are folded inward twice, is the condition that sleeves are not rolled up met? | added: new boundary question where today's row has none |
| dafi36-2903 7.1.5 | Can only be worn with the formal dress, mess dress, Class A, semi-formal dress, and Class B uniforms. | (none) | When a topcoat or all-weather coat is worn with the formal dress, mess dress, Class A, semi-formal dress, and Class B uniforms, was it worn only in those specified uniform types? | added: new boundary question where today's row has none |
| dafi36-2903 7.1.6 | A coyote brown fleece liner may be worn under the OCP jacket; however, the fleece liner will not be visible. | (none) | When a member wears a coyote brown fleece liner under the OCP jacket, is the fleece liner not visible? | added: new boundary question where today's row has none |
| dafi36-2903 7.1.7 | Note: Airmen may sew-on or use Velcro® backing for nametape, USAF tape, and rank but will not mix sewn-on and Velcro® tapes or rank. | (none) | When Airmen sew-on or use Velcro® backing for nametape, USAF tape, and rank, do they not mix sewn-on and Velcro® tapes or rank? | added: new boundary question where today's row has none |
| dafi36-2903 7.3.5.2 | Use of a shoulder strap is authorized on either shoulder, or the strap may cross the body so long as it does not interfere with rendering t... | (none) | When a unit uses a shoulder strap on either shoulder, or the strap crosses the body, does it not interfere with rendering the proper salute? | added: new boundary question where today's row has none |
| dafi36-2903 7.3.8.1 | Only black gloves may be worn with the service dress uniform and all approved outer garments worn with the dress uniforms. | (none) | When a unit wears black gloves with the service dress uniform and all approved outer garments worn with the dress uniforms, were only black gloves worn? | added: new boundary question where today's row has none |
| dafi36-2903 7.4.1.2 | Airmen may wear taps on their shoes to preserve the heels as long as the taps do not change the intended appearance of the shoes. | (none) | When Airmen wear taps on their shoes to preserve the heels, do the taps not change the intended appearance of the shoes? | added: new boundary question where today's row has none |
| dafi36-2903 8.1.7.1 | Installation commanders may authorize wear of an optional solid black, white, or dark blue baseball/sport cap and/or sweatband with the Air... | (none) | When installation commanders authorize wear of an optional solid black, white, or dark blue baseball/sport cap and/or sweatband with the Air Force symbol or U.S. Air Force printed/embroidered on the front, is it during organized PT? | added: new boundary question where today's row has none |
| dafi36-2903 8.1.9 | Cold weather accessories may be worn outdoors only. | (none) | When cold weather accessories are worn outdoors, were they worn only outdoors? | added: new boundary question where today's row has none |
| dafi36-2903 9.12.2.10 | Commander's Insignia may be worn for officers in the rank of Colonel (O-6) and below when currently in command, as authorized by AFMAN 36-2... | (none) | When an officer wears Commander's Insignia for officers in the rank of Colonel (O-6) and below when currently in command, is it as authorized by AFMAN 36-2100, Military Utilization and Classification? | added: new boundary question where today's row has none |
| dafi36-2903 9.12.2.14.2 | At Remote Pilot Aircraft designated units, commanders may authorize the wear of the fleece jackets inside the ground shelters. | (none) | When commanders authorize the wear of the fleece jackets inside the ground shelters at Remote Pilot Aircraft designated units, is this authorized? | added: new boundary question where today's row has none |
| dafi36-2903 9.12.3.4 | A single knife with clip may be secured inside a trouser pocket with the clip exposed provided no more than the clip is exposed and the kni... | (none) | When a single knife with clip is secured inside a trouser pocket with the clip exposed, provided no more than the clip is exposed and the knife is a subdued or matte color, was the limit met? | added: new boundary question where today's row has none |

### "Recommended, not required" labels on the fresh document

| Row | Source text | Question |
|---|---|---|
| dafi36-2903 1.2.9 | Headgear should also be worn indoors by armed Security Forces personnel or others bearing arms while performing duties. | (none) |
| dafi36-2903 1.3.1.1 | When traveling in an official capacity on commercial air overseas, Airmen should first consult the Department of Defense Foreign Clearance Guide befo... | (none) |
| dafi36-2903 10.3.1 (inferred) | During inclement or extreme weather, commanders should authorize the | (none) |
| dafi36-2903 10.3.1.2 | When responding to indoor situations, armed Security Forces (SF) personnel should wear the appropriate headgear based on the overall situation (e.g.,... | (none) |
| dafi36-2903 10.6.1 | All accessories and medals should be like-new and clean. | (none) |
| dafi36-2903 10.6.4 | Spurs should be silver and non-ornamental. | (none) |
| dafi36-2903 11.4 (inferred) | All approved religious accommodations should be worn in a neat and conservative manner (defined as, discreet, tidy, and not dissonant or showy in sty... | (none) |
| dafi36-2903 11.4.2 | Beards should follow the natural contours of the face and be groomed in a neat and conservative manner that presents a professional military image an... | (none) |
| dafi36-2903 12.8.1 | New patch/tab requests should follow guidance as outlined in para 12.7.3.1 through 12.7.3.4. | (none) |
| dafi36-2903 2.17.7 | Note: Members should also consult AFI 34-1201, Protocol, for protocol, customs, and courtesies. | (none) |
| dafi36-2903 3.2.1 | Commanders should contact their servicing Air Force Office of Special Investigations (AFOSI) unit for additional information on potential identificat... | (none) |
| dafi36-2903 5.1.5.1.5.2 | Wear sister service badges according to the applicable Service order of precedence however, all Air Force badges take precedence over sister service ... | (none) |
| dafi36-2903 7.1.10 | Maternity cold-weather outerwear should be either OCP-patterned or solid black, dark blue, dark green, dark brown, or coyote brown in color (Note: So... | (none) |
| dafi36-2903 9.1.3 | Organizations requiring exception to FDU/DFDU wear policy should submit an Exception to Policy request through their MAJCOM/A3 or equivalent channels... | (none) |
| dafi36-2903 9.12.2.19 | Socks should be made of cotton or wool. | (none) |
| dafi36-2903 9.12.2.9.2.1 | The Tactical Call Sign Duty Identifier patch should only be worn for tactical (radio) call signs assigned/ordered by the unit commander. | (none) |
| dafi36-2903 9.8 | Socks should be made of cotton or wool. | (none) |

### Pointer rows on the fresh document

| Row | Source text | Today's question | Decision |
|---|---|---|---|
| dafi36-2903 1.2.5 | Refer to Title 10 USC Section 772, When wearing by persons not on active duty authorized. | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |
| dafi36-2903 3.1.1.4 | Males only: dreadlocks, coils, braids, twists, designs, and/or hair extensions are not authorized; see Figure 3.1 for examples. | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |
| dafi36-2903 4.4.1 | For wear description see paragraph 4.5.2. | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |
| dafi36-2903 5.1.5.1.3 | When three badges are worn, they are centered 1/8-inch above the U.S. Air Force tape either in a single vertical column with 1/4-inch between badges; or two badges are w... | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |
| dafi36-2903 5.1.5.1.5 | Authorized cold weather accessories for the OCP are: Coyote Brown fleece may be worn, see paragraph 7.1.7, for additional guidance. | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |
| dafi36-2903 6.2.2 | For wear description see paragraph 4.2.1. | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |
| dafi36-2903 6.2.3 | For wear description see paragraph 6.4.3. | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |
| dafi36-2903 6.5.4 | For wear description for the OCP refer to paragraphs 5.1.2 through 5.1.6.2.4. | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |
| dafi36-2903 9.2.1 | Additionally, guidance for Rated Officers assigned to an Aircrew Position Identifier-0 and Career Enlisted Aviators assigned to Aircrew Position Identifier-Z positions t... | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |
| dafi36-2903 9.5.2 | Authorized individuals are listed in paragraph 9.5.2.3 and paragraph 10.7.6. | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |
| dafi36-2903 9.6.3 | Exception: When approved by MAJCOM/CC, aerial demonstration teams, and competitive teams may wear organizational caps while engaged in demonstration and competitions see... | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |
| dafi36-2903 9.12.2.9.2.1 | Authorized Duty Identifier Patches are listed in Table 5.1 (Note: Only patches listed in Table 5.1 are authorized. | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |
| dafi36-2903 9.12.2.14.5 | Authorized individuals are listed in paragraph 9.5.2.3 and paragraph 10.7.6. | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |
| dafi36-2903 12.1 | If earned, wear only one foreign badge (see paragraph 5.1.5.1.3 for additional information). | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |
| dafi36-2903 12.8.4 | Wear guidance is outlined in paragraph 5.1.6.2.3. | (none) | pointer (suppress: only points to another place (a pointer states no duty of its own; the duty is wherever it... |

### Where the checks rejected a model question on the fresh document

| Row | Source text | Model's question | Why | Today's question |
|---|---|---|---|---|
| dafi36-2903 (no number) | An OCP Velcro® sleeve pen/pencil holder may be worn on either sleeve but will not impede the proper wear of required patches and/... | When an OCP Velcro® sleeve pen/pencil holder is worn on either sleeve, does it not impede the proper wear of required patches and/or duty badges? | model question rejected: the question asks whether the permitted act ('required') happened instead of whether its limit... | (none) |
| dafi36-2903 10.5.5 | Airman may wear a lab coat or smock as designated by the Medical Treatment Facility Commander. | When an airman wears a lab coat or smock, was it designated by the Medical Treatment Facility Commander? | model question rejected: the question asks whether the permitted act ('designated') happened instead of whether its lim... | (none) |
| dafi36-2903 2.17.6 | Public displays of affection are inappropriate as they violate a long-standing custom of the service and may be service discredit... | When Airmen engage in brief displays of affection, such as a modest kiss or embrace, in situations where physical contact is commonly accepted etiquette such as weddings, graduations, promotions, or ... | model question rejected: question drops the trigger or actor of the permission | (none) |
| dafi36-2903 3.1.5 | Female Airmen may wear conservatively styled cosmetics. | When Female Airmen wear cosmetics, are they conservatively styled? | model question rejected: the question asks whether the permitted act ('styled') happened instead of whether its limit w... | (none) |
| dafi36-2903 5.1.1 | Note: Commanders may authorize the coat to be tucked in for duty (e.g., Security Forces Airmen) if necessary. | When commanders authorize the coat to be tucked in for duty (e.g., Security Forces Airmen), was it done if necessary? | model question rejected: limit is only a adverb | (none) |
| dafi36-2903 5.1.6 | Sister service and joint organization badges/patches can be worn in their current color configuration and will not be converted t... | When Airmen assigned, attached, detailed, or activated in support of sister service units or joint organizations wear sister service's or joint organization's organizational badges/patches in their c... | model question rejected: the question asks whether the permitted act ('converted') happened instead of whether its limi... | (none) |
| dafi36-2903 8.1.4.3 | Short and long sleeved form fitting undershirts, (i.e., spandex, Lycra® or elastic material) to include those with a mock neck ma... | When short and long sleeved form fitting undershirts, (i.e., spandex, Lycra® or elastic material) to include those with a mock neck are worn and visible under the PTG sweatshirt, is it done only at n... | model question rejected: the question asks whether the permitted act ('worn') happened instead of whether its limit was... | (none) |
| dafi36-2903 9.12.2.11 | Airmen performing flight duties in a deployed environment may remove all or some patches in accordance with mission directives. | When Airmen performing flight duties in a deployed environment remove all or some patches, is it in accordance with mission directives? | model question rejected: limit only points at 'applicable provisions' (always yes) | (none) |
| dafi36-2903 9.12.2.13 (inferred) | Deployed Airmen, or Airmen as authorized by MAJCOM, may wear the OCP boonie (campaign/floppy) hat when theater conditions dictate. | When Deployed Airmen, or Airmen as authorized by MAJCOM wear the OCP boonie (campaign/floppy) hat when theater conditions dictate, is there compliance with theater conditions? | model question rejected: the question asks whether the permitted act ('wear') happened instead of whether its limit was... | (none) |
| dafi36-2903 9.12.2.9.2.4 | An OCP Velcro® sleeve pen/pencil holder may be worn on either sleeve but will not impede the proper wear of required patches and/... | When an OCP Velcro® sleeve pen/pencil holder is worn on either sleeve, does it not impede the proper wear of required patches and/or duty badges? | model question rejected: the question asks whether the permitted act ('required') happened instead of whether its limit... | (none) |
| dafi36-2903 9.3.1 | HAF staff personnel may wear the FDU/DFDU configured as directed by the Deputy Chief of Staff (DCS) or equivalent. | When HAF staff personnel wear the FDU/DFDU, was it configured as directed by the Deputy Chief of Staff (DCS) or equivalent? | model question rejected: the question asks whether the permitted act ('configured') happened instead of whether its lim... | (none) |
| dafi36-2903 9.3.7 | The flight cap may be stored in either lower leg pocket without that pocket being fully zipped. | When the flight cap is stored in either lower leg pocket, is it true that without that pocket being fully zipped? | model question rejected: the question asks whether the permitted act ('zipped') happened instead of whether its limit w... | (none) |
| dafi36-2903 9.5.2.2 | Members may add an inside pocket, at their expense, when it does not detract from the external appearance. | When members add an inside pocket at their expense, when it does not detract from the external appearance, is there any condition that needs to be met? | model question rejected: C4_turns_may_into_duty | (none) |

## What still looks wrong

(Counts and what I can see in the tables; not quality grades.)

1. **Fresh-document coverage is partial:** 218 gate-passing permission rows were not asked because of the call budget. Their questions are today's. The result is a sample, not the whole document.
2. **Most permission rows add nothing.** On the fresh document 18 questions were added and 0 replaced out of 92 asked; 0 rows ended at today's question (the model's question was rejected, not clearly better, or none).
2b. **The fresh document had no live questions at all** (every row's today's question is empty), so on dafi36-2903 the additive-only policy is not really tested: all 18 changes are additions to blank rows, and nothing could be kept, replaced or removed.
2c. **Pointer rule: real duties are marked "no question" on the fresh document.** The 15 suppressions include rows that also state a rule: dafi36-2903 3.1.1.4 ("Males only: dreadlocks ... are not authorized; see Figure 3.1"), 5.1.5.1.3 (how three badges are centred), 9.6.3 (an exception for aerial demonstration teams), 12.1 ("wear only one foreign badge"), 9.12.2.9.2.1 ("Only patches listed in Table 5.1 are authorized"), and 5.1.5.1.5 (a fleece "may be worn"). No live question was lost (there were none), but the pre-registered target (no pointer suppression that removes a real duty) is NOT met here. The pointer rule detects a duty by a duty word or a leading command; "are not authorized", "when ... they are centered" and "wear only" slip through.
2d. **The checks rejected 13 of 31 model questions on the fresh document (42%), against 16% on the seven documents.** A higher rate on a new document is the over-fitting warning I set. Several rejections look wrong: the may-to-duty check refused "When an airman wears a lab coat or smock, was it designated by the Medical Treatment Facility Commander?" and "When HAF staff personnel wear the FDU/DFDU, was it configured as directed by ...?" because the verb that follows the may is the limit itself ("as designated by"). I did not change anything after the freeze.
2e. **Some added questions are thin or awkward** (read the table): 7.3.5.2 ("... does it not interfere with rendering the proper salute?", a double negative), 5.1.1 ("is the condition that sleeves are not rolled up met?"), 9.12.2.14.2 ("... is this authorized?", which restates the permission), 9.12.3.4 ("was the limit met?"), 8.1.7.1 (the limit chosen is "during organized PT", which is only one of several conditions).
3. **Today's questions that turn a "may" into "does the unit" now stay.** That follows the additive-only rule. They are listed as "kept"; a reviewer should decide how many of them are wrong.
4. **The gates and checks were written after reading the AFI and seven-document rows,** and the three reviewer cases were tuned for. The fresh document is the only independent check, and it is a single document of a different style (dress and appearance).
5. **Replacement test is a word-count proxy.** "Clearly better" means the new question carries the limit's words and today's does not; it can replace a good but differently worded question.
6. **Removals** are limited to bare capability / invented questions where no limit was found; whether those were truly of no use is for the reviewer.
7. **Doc gate is a blunt percentage** (25%). A short guidance document with few permission rows would not be caught.

