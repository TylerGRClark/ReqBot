"""Write report.md (round 5, plain words, for Tyler) from outputs/round5_*.json. No model, no grades."""
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
R = json.loads((OUT / "round5_regress_rows.json").read_text())
RS = json.loads((OUT / "round5_regress_summary.json").read_text())
F = json.loads((OUT / "round5_fresh_rows.json").read_text())
FS = json.loads((OUT / "round5_fresh_summary.json").read_text())

if (HERE / "report.md").exists() and not (HERE / "report_round4.md").exists():
    shutil.copy(HERE / "report.md", HERE / "report_round4.md")


def cut(t, n=230):
    t = (t or "").replace("|", "/").replace("\n", " ").strip()
    return t if len(t) <= n else t[: n - 1] + "..."


def short(e):
    return f"{e['doc']} {e['citation'] or '(no number)'}"


def changed_perm(rows):
    return sorted((e for e in rows if e["action"] in ("added", "replaced", "removed_capability")), key=lambda e: (e["doc"], e["citation"] or "", e["source_quote"]))


def table(rows, title):
    L = [title, "", "| Row | Source text | Today's question | New question | What happened |", "|---|---|---|---|---|"]
    for e in rows:
        L.append(f"| {short(e)} | {cut(e['source_quote'], 140)} | {cut(e['live_question']) if e['live_question'] else '(none)'} | {cut(e['final_question'], 300) if e['final_question'] else '(no question)'} | {e['action']}: {cut(e['rule'], 120)}{'; ' + '; '.join(e['notes']) if e['notes'] else ''} |")
    return L + [""]


tot_fresh = FS["documents"]["dafi36-2903"]
rate_r, rate_f = RS["check_rejection_rate"], FS["check_rejection_rate"]
L = ["# Kind-aware draft audit questions, round 5: report for Tyler", "",
     "Plain words. Nothing in the live checklist or index was touched. Earlier reports are kept: `report_round1.md`, `report_round3.md`, `report_round4.md`. **I do not grade questions.** The seven documents used in round 4 are no longer a clean test (their rows drove these fixes); the fresh document below is the only clean test left, and it was run once with the rules frozen first.", ""]
L += ["## The short version", "",
      "- **Today's questions are no longer deleted.** The new rule can only add a question where a row has none, or replace today's question when the new one clearly carries the stated limit and today's does not. The only removals allowed are a bare \"Can X ...?\" question or an invented \"consent / recognize\" question; each is listed.",
      f"- **Seven documents (regression):** {RS['rows']} rows, 0 dropped; {RS['model_calls_cumulative']} model calls in total. Rows whose question changed: " + str(sum(1 for e in R if e["action"] in ("added", "replaced"))) + f" added or replaced, {len(RS['removals'])} removed (both are \"consent\" questions in DODI 5200.48 3.10), {sum(1 for e in R if e['action'] == 'pointer_suppress')} pointer suppressions, {sum(1 for e in R if e['action'] == 'label')} \"recommended\" labels.",
      "- **The three missed limits the reviewer named** now get a question (listed below). They were tuned for, so they are regression cases and not evidence the rules generalise.",
      f"- **Fresh document dafi36-2903** ({tot_fresh['rows_in_document']} rows, {tot_fresh['permission_rows']} classed as permission): {FS['asked']} gate-passing permission rows were asked of the model; the other {FS['not_sampled']} were not asked (call budget) and keep today's question. {tot_fresh['added']} questions added, {tot_fresh['replaced']} replaced, {tot_fresh['kept_live']} left at today's, {tot_fresh['removed_capability_or_invented']} removed, {tot_fresh['labels']} \"recommended\" labels, {tot_fresh['pointer_suppressed']} pointer suppressions.",
      f"- **Mechanical checks:** among accepted new questions, 0 drop a number or qualifier, 0 turn a \"may\" into a happened-fact, 0 start with a bare \"this/it\". The checks rejected {rate_r['rejected']} of {rate_r['model_questions']} model questions on the seven documents and {rate_f['rejected']} of {rate_f['model_questions']} on the fresh one.", ""]
L += ["## The fixes, in plain words", "",
      "1. **Additive only** (above).",
      "2. **\"Such as\" and \"such cases\" are no longer treated as a missing reference** unless \"such\" opens the question.",
      "3. **The rule only fires when may/can is the main verb of the sentence.** Test used: take the sentence holding the may/can; drop an opening \"When ...,\" clause; look only at what follows the last colon or semicolon; the words before the may/can must contain no \"that/which/if/when/unless/because\", no \"shall/must/will/should/need to/ensure\", no \"No ...\"/\"unless\"/\"may not\", must not start with a command verb (a role bullet like \"Administers ...\"), and be 25 words or fewer; and the words after must not be \"include / vary / need / contain / require\". Rows that fail keep today's question and the model is not even asked.",
      "4. **A new question may not ask whether the permitted act happened** (\"may be used\" turned into \"was used\"). Mechanical: a verb that follows the source's may/can may not appear only in the asked half of the question.",
      "5. **Guidance documents are left alone.** Test: permission + recommendation rows are at least 25% of the document's rows. This excludes NIST.SP.800-125 (38%). Every other document is under 8%; dafi36-2903 is 16% so it is not excluded. For an excluded document today's questions stay and the \"recommended\" labels still apply.", ""]
L += ["## Which documents the gate excludes", "", "| Document | Rows | Permission + recommendation share | Permission path |", "|---|---|---|---|"]
for d, v in {**RS["documents"], **FS["documents"]}.items():
    L.append(f"| {d} | {v['rows_in_document']} | {v['permission_plus_recommendation_share']:.0%} | {'ON' if v['document_gate_allows_permission_path'] else 'OFF (guidance prose)'} |")
L += ["", "## Seven documents (regression; no longer a clean test)", "",
      "| Document | Rows | Permission rows | Stopped by the main-verb gate | Asked | Added | Replaced | Today's kept | Removed | Pointers suppressed | Labels |", "|---|---|---|---|---|---|---|---|---|---|---|"]
for d, v in RS["documents"].items():
    asked = v["model_calls"]
    L.append(f"| {d} | {v['rows_in_document']} | {v['permission_rows']} | {v['gated_out_main_verb'] + v['doc_gated']} | {asked} | {v['added']} | {v['replaced']} | {v['kept_live']} | {v['removed_capability_or_invented']} | {v['pointer_suppressed']} | {v['labels']} |")
L += [""]
L += table(changed_perm(R), "### Every permission row whose question changed from today's (seven documents)")
reg_cases = [e for e in R if (e["doc"] == "DODI 8551.01" and "OIG DoD may attend" in e["source_quote"]) or (e["doc"] == "DODI 5200.48" and ("first class mail" in e["source_quote"] or ("DoD CUI may be disseminated to DoD personnel" in e["source_quote"])))]
L += table(sorted(reg_cases, key=lambda e: (e["doc"], e["source_quote"])), "### The reviewer's three missed-limit cases (regression cases, tuned for)")
L += ["### Rows where the permission path found nothing and today's question stays, or there was none", "",
      f"Seven documents: {sum(1 for e in R if e['action'] == 'kept_live')} rows keep today's question after the model's question was rejected or not clearly better; {sum(1 for e in R if e['action'] == 'none')} rows have no question before and none after. The complete row list is in `outputs/round5_regress_rows.json`.", ""]
L += ["### Pointer suppressions (read by hand, as before)", ""] + [f"- {short(e)}: \"{cut(e['source_quote'], 120)}\" (today's question: {cut(e['live_question'], 90) if e['live_question'] else 'none'}). No duty." for e in R if e["action"] == "pointer_suppress"] + [""]
L += ["## Fresh document: dafi36-2903 (the clean test, run once with the rules frozen)", "",
      f"Rows processed: permission, recommendation and pointer rows only ({FS['rows']} of {tot_fresh['rows_in_document']}). Permission rows: {tot_fresh['permission_rows']}; stopped by the main-verb gate: {tot_fresh['gated_out_main_verb']}; asked: {FS['asked']} (fixed order by SHA-1 of the row id, because the call budget did not cover every gate-passing row); not asked: {FS['not_sampled']}. "
      f"Model calls this round (cumulative): {RS['model_calls_cumulative'] + FS['model_calls']}.", ""]
L += table(changed_perm(F), "### Every permission row whose question changed from today's (fresh document)")
L += ["### \"Recommended, not required\" labels on the fresh document", "", "| Row | Source text | Question |", "|---|---|---|"]
for e in sorted([e for e in F if e["action"] == "label"], key=lambda e: e["citation"] or ""):
    L.append(f"| {short(e)} | {cut(e['source_quote'], 150)} | {cut(e['live_question'], 150) if e['live_question'] else '(none)'} |")
L += ["", "### Pointer rows on the fresh document", "", "| Row | Source text | Today's question | Decision |", "|---|---|---|---|"]
for e in F:
    if (e["action"] or "").startswith("pointer"):
        L.append(f"| {short(e)} | {cut(e['source_quote'], 170)} | {cut(e['live_question'], 120) if e['live_question'] else '(none)'} | {cut(e['rule'], 110)} |")
L += ["", "### Where the checks rejected a model question on the fresh document", "", "| Row | Source text | Model's question | Why | Today's question |", "|---|---|---|---|---|"]
for e in sorted([e for e in F if e["model_question_rejected"]], key=lambda e: e["citation"] or ""):
    L.append(f"| {short(e)} | {cut(e['source_quote'], 130)} | {cut(e.get('model_question_raw'), 200)} | {cut('; '.join(e['notes']), 120)} | {cut(e['live_question'], 110) if e['live_question'] else '(none)'} |")
kept = sum(1 for e in F if e["action"] == "kept_live")
L += ["", "## What still looks wrong", "",
      "(Counts and what I can see in the tables; not quality grades.)", "",
      f"1. **Fresh-document coverage is partial:** {FS['not_sampled']} gate-passing permission rows were not asked because of the call budget. Their questions are today's. The result is a sample, not the whole document.",
      f"2. **Most permission rows add nothing.** On the fresh document {tot_fresh['added']} questions were added and {tot_fresh['replaced']} replaced out of {FS['asked']} asked; {kept} rows ended at today's question (the model's question was rejected, not clearly better, or none).",
      f"2b. **The fresh document had no live questions at all** (every row's today's question is empty), so on dafi36-2903 the additive-only policy is not really tested: all {tot_fresh['added']} changes are additions to blank rows, and nothing could be kept, replaced or removed.",
      f"2c. **Pointer rule: real duties are marked \"no question\" on the fresh document.** The {tot_fresh['pointer_suppressed']} suppressions include rows that also state a rule: dafi36-2903 3.1.1.4 (\"Males only: dreadlocks ... are not authorized; see Figure 3.1\"), 5.1.5.1.3 (how three badges are centred), 9.6.3 (an exception for aerial demonstration teams), 12.1 (\"wear only one foreign badge\"), 9.12.2.9.2.1 (\"Only patches listed in Table 5.1 are authorized\"), and 5.1.5.1.5 (a fleece \"may be worn\"). No live question was lost (there were none), but the pre-registered target (no pointer suppression that removes a real duty) is NOT met here. The pointer rule detects a duty by a duty word or a leading command; \"are not authorized\", \"when ... they are centered\" and \"wear only\" slip through.",
      f"2d. **The checks rejected {rate_f['rejected']} of {rate_f['model_questions']} model questions on the fresh document ({round(100 * rate_f['rejected'] / max(1, rate_f['model_questions']))}%), against {round(100 * rate_r['rejected'] / max(1, rate_r['model_questions']))}% on the seven documents.** A higher rate on a new document is the over-fitting warning I set. Several rejections look wrong: the may-to-duty check refused \"When an airman wears a lab coat or smock, was it designated by the Medical Treatment Facility Commander?\" and \"When HAF staff personnel wear the FDU/DFDU, was it configured as directed by ...?\" because the verb that follows the may is the limit itself (\"as designated by\"). I did not change anything after the freeze.",
      "2e. **Some added questions are thin or awkward** (read the table): 7.3.5.2 (\"... does it not interfere with rendering the proper salute?\", a double negative), 5.1.1 (\"is the condition that sleeves are not rolled up met?\"), 9.12.2.14.2 (\"... is this authorized?\", which restates the permission), 9.12.3.4 (\"was the limit met?\"), 8.1.7.1 (the limit chosen is \"during organized PT\", which is only one of several conditions).",
      "3. **Today's questions that turn a \"may\" into \"does the unit\" now stay.** That follows the additive-only rule. They are listed as \"kept\"; a reviewer should decide how many of them are wrong.",
      "4. **The gates and checks were written after reading the AFI and seven-document rows,** and the three reviewer cases were tuned for. The fresh document is the only independent check, and it is a single document of a different style (dress and appearance).",
      "5. **Replacement test is a word-count proxy.** \"Clearly better\" means the new question carries the limit's words and today's does not; it can replace a good but differently worded question.",
      "6. **Removals** are limited to bare capability / invented questions where no limit was found; whether those were truly of no use is for the reviewer.",
      "7. **Doc gate is a blunt percentage** (25%). A short guidance document with few permission rows would not be caught.", ""]
(HERE / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("report written", len(L))
