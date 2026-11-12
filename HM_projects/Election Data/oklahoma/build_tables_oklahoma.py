#!/usr/bin/env python3
"""
Oklahoma county results CSV (20261103_CountyResults.csv) -> class tables (pandas).

  county_table.csv:    election_date,state,county_name,county_fips,ballots_cast,registered_voters
  contest_table.csv:   election_date,state,county_name,county_fips,office,contest_id,candidate,party,votes
  contest_reference.csv  (helper) one row per contest_id: source race number/description, jurisdiction, scope
  notes.txt

Usage:
  python build_tables_oklahoma.py 20261103_CountyResults.csv [--outdir out_ok] [--turnout turnout.csv]

  --turnout  optional CSV: county_name,ballots_cast,registered_voters (official county-wide figures;
             the results file has neither)
"""
import argparse, re, sys
from pathlib import Path
import pandas as pd

STATE = "OK"

# Oklahoma counties: source name (as written in the file) -> (display name, county FIPS)
COUNTIES = {
    "ADAIR": ("Adair", "40001"), "ALFALFA": ("Alfalfa", "40003"), "ATOKA": ("Atoka", "40005"),
    "BEAVER": ("Beaver", "40007"), "BECKHAM": ("Beckham", "40009"), "BLAINE": ("Blaine", "40011"),
    "BRYAN": ("Bryan", "40013"), "CADDO": ("Caddo", "40015"), "CANADIAN": ("Canadian", "40017"),
    "CARTER": ("Carter", "40019"), "CHEROKEE": ("Cherokee", "40021"), "CHOCTAW": ("Choctaw", "40023"),
    "CIMARRON": ("Cimarron", "40025"), "CLEVELAND": ("Cleveland", "40027"), "COAL": ("Coal", "40029"),
    "COMANCHE": ("Comanche", "40031"), "COTTON": ("Cotton", "40033"), "CRAIG": ("Craig", "40035"),
    "CREEK": ("Creek", "40037"), "CUSTER": ("Custer", "40039"), "DELAWARE": ("Delaware", "40041"),
    "DEWEY": ("Dewey", "40043"), "ELLIS": ("Ellis", "40045"), "GARFIELD": ("Garfield", "40047"),
    "GARVIN": ("Garvin", "40049"), "GRADY": ("Grady", "40051"), "GRANT": ("Grant", "40053"),
    "GREER": ("Greer", "40055"), "HARMON": ("Harmon", "40057"), "HARPER": ("Harper", "40059"),
    "HASKELL": ("Haskell", "40061"), "HUGHES": ("Hughes", "40063"), "JACKSON": ("Jackson", "40065"),
    "JEFFERSON": ("Jefferson", "40067"), "JOHNSTON": ("Johnston", "40069"), "KAY": ("Kay", "40071"),
    "KINGFISHER": ("Kingfisher", "40073"), "KIOWA": ("Kiowa", "40075"), "LATIMER": ("Latimer", "40077"),
    "LEFLORE": ("Le Flore", "40079"), "LINCOLN": ("Lincoln", "40081"), "LOGAN": ("Logan", "40083"),
    "LOVE": ("Love", "40085"), "MCCLAIN": ("McClain", "40087"), "MCCURTAIN": ("McCurtain", "40089"),
    "MCINTOSH": ("McIntosh", "40091"), "MAJOR": ("Major", "40093"), "MARSHALL": ("Marshall", "40095"),
    "MAYES": ("Mayes", "40097"), "MURRAY": ("Murray", "40099"), "MUSKOGEE": ("Muskogee", "40101"),
    "NOBLE": ("Noble", "40103"), "NOWATA": ("Nowata", "40105"), "OKFUSKEE": ("Okfuskee", "40107"),
    "OKLAHOMA": ("Oklahoma", "40109"), "OKMULGEE": ("Okmulgee", "40111"), "OSAGE": ("Osage", "40113"),
    "OTTAWA": ("Ottawa", "40115"), "PAWNEE": ("Pawnee", "40117"), "PAYNE": ("Payne", "40119"),
    "PITTSBURG": ("Pittsburg", "40121"), "PONTOTOC": ("Pontotoc", "40123"),
    "POTTAWATOMIE": ("Pottawatomie", "40125"), "PUSHMATAHA": ("Pushmataha", "40127"),
    "ROGER MILLS": ("Roger Mills", "40129"), "ROGERS": ("Rogers", "40131"),
    "SEMINOLE": ("Seminole", "40133"), "SEQUOYAH": ("Sequoyah", "40135"),
    "STEPHENS": ("Stephens", "40137"), "TEXAS": ("Texas", "40139"), "TILLMAN": ("Tillman", "40141"),
    "TULSA": ("Tulsa", "40143"), "WAGONER": ("Wagoner", "40145"), "WASHINGTON": ("Washington", "40147"),
    "WASHITA": ("Washita", "40149"), "WOODS": ("Woods", "40151"), "WOODWARD": ("Woodward", "40153"),
}

CONTEST_COLS = ["election_date", "state", "county_name", "county_fips",
                "office", "contest_id", "candidate", "party", "votes"]
COUNTY_COLS = ["election_date", "state", "county_name", "county_fips",
               "ballots_cast", "registered_voters"]

STATEWIDE = {  # normalized description (without leading "FOR ") -> contest code
    "GOVERNOR": "GOV", "LIEUTENANT GOVERNOR": "LTGOV", "ATTORNEY GENERAL": "AG",
    "STATE TREASURER": "TREAS", "SUPERINTENDENT OF PUBLIC INSTRUCTION": "SPI",
    "COMMISSIONER OF LABOR": "LABOR", "INSURANCE COMMISSIONER": "INS",
    "CORPORATION COMMISSIONER": "CORPCOMM", "UNITED STATES SENATOR": "USS-regular",
}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def is_measure(options: set) -> bool:
    return any(o.upper().endswith(("YES", "- YES")) for o in options) and \
           any(o.upper().endswith("NO") for o in options)


def base_contest_id(desc: str, entity: str, county_fips: str, year: str, measure: bool) -> str:
    """Readable ID from the source description; uniqueness is enforced by the caller."""
    d = norm(desc)
    pre = f"{year}-{STATE}-"
    unexpired = "-unexpired" if "UNEXPIRED TERM" in d else ""
    core = re.sub(r"^FOR ", "", d)
    core = re.sub(r"\s*\(UNEXPIRED TERM\)", "", core)

    if core in STATEWIDE:
        return pre + STATEWIDE[core]
    if m := re.fullmatch(r"UNITED STATES REPRESENTATIVE DISTRICT (\d+)", core):
        return f"{pre}USH-{int(m[1])}"
    if m := re.fullmatch(r"STATE SENATOR DISTRICT (\d+)", core):
        return f"{pre}STS-{int(m[1])}{unexpired}"
    if m := re.fullmatch(r"STATE REPRESENTATIVE DISTRICT (\d+)", core):
        return f"{pre}STH-{int(m[1])}{unexpired}"
    if m := re.fullmatch(r"DISTRICT JUDGE DISTRICT (\d+), OFFICE (\d+)", core):
        return f"{pre}DJ-{int(m[1])}-{int(m[2])}"
    if m := re.fullmatch(r"ASSOCIATE DISTRICT JUDGE (.+) COUNTY", core):
        return f"{pre}ADJ-{slug(m[1])}"
    if m := re.fullmatch(r"SUPREME COURT DISTRICT (\d+)", core):
        return f"{pre}SC-{int(m[1])}-retention"
    if m := re.fullmatch(r"COURT OF CRIMINAL APPEALS DISTRICT (\d+)", core):
        return f"{pre}CCA-{int(m[1])}-retention"
    if m := re.fullmatch(r"COURT OF CIVIL APPEALS DISTRICT (\d+) - OFFICE (\d+)", core):
        return f"{pre}CIVAPP-{int(m[1])}-{int(m[2])}-retention"
    if m := re.match(r"STATE QUESTION NO\. (\d+)", core):
        return f"{pre}SQ-{m[1]}"

    ent = norm(entity)
    if ent.endswith(" COUNTY"):                         # county-level office or measure
        c = f"{pre}county-{county_fips[2:]}"
        if m := re.fullmatch(r"COUNTY COMMISSIONER DISTRICT NO\. (\d+)", core):
            return f"{c}-commissioner-{m[1]}"
        if m := re.fullmatch(r"COUNTY (ASSESSOR|TREASURER|SHERIFF)", core):
            return f"{c}-{m[1].lower()}{unexpired}"
        if m := re.fullmatch(r"PROPOSITION(?: NO\. (\d+))?", core):
            return f"{c}-measure-{m[1]}" if m[1] else f"{c}-measure"
        return f"{c}-{slug(core)}{unexpired}"
    # municipality / special district: jurisdiction slug + office slug (entity text removed)
    local = norm(core.replace(ent, ""))
    return f"{pre}{slug(ent)}-{slug(local)}{unexpired}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--outdir", default="out_ok")
    ap.add_argument("--turnout")
    a = ap.parse_args()
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)

    # The file has one more field per row than header names (trailing comma) -> name columns explicitly.
    cols = pd.read_csv(a.csv, nrows=0).columns.tolist()
    raw = pd.read_csv(a.csv, header=0, names=cols + ["_extra"], dtype=str, keep_default_na=False)
    raw = raw.drop(columns="_extra")
    for c in raw.columns:
        raw[c] = raw[c].str.strip()

    # ---- validation -------------------------------------------------------------------
    unknown = sorted(set(raw["county"]) - set(COUNTIES))
    if unknown:
        sys.exit(f"ERROR: counties without FIPS mapping: {unknown}")
    num = {c: pd.to_numeric(raw[c], errors="coerce")
           for c in ["cand_absmail_votes", "cand_early_votes", "cand_elecday_votes", "cand_tot_votes"]}
    comp_bad = int(((num["cand_absmail_votes"] + num["cand_early_votes"] + num["cand_elecday_votes"])
                    != num["cand_tot_votes"]).sum())
    missing = int(num["cand_tot_votes"].isna().sum())
    negative = int((num["cand_tot_votes"] < 0).sum())
    partial = int((raw["tot_race_prec"] != raw["race_prec_reporting"]).sum())
    dups = int(raw.duplicated(["county", "entity_description", "race_number", "cand_number"]).sum())

    election_date = pd.to_datetime(raw["elec_date"].unique()[0], format="%m/%d/%Y").strftime("%Y-%m-%d")
    year = election_date[:4]
    assert raw["elec_date"].nunique() == 1, "multiple election dates in file"

    # ---- contest ids (one per race_number; same id across all county rows of that race) ----
    races = (raw.assign(county_fips=raw["county"].map(lambda c: COUNTIES[c][1]))
                .groupby("race_number", sort=True)
                .agg(desc=("race_description", "first"), entity=("entity_description", "first"),
                     fips=("county_fips", "first"),
                     options=("cand_name", lambda s: set(s)),
                     n_entities=("entity_description", "nunique"),
                     counties=("county", lambda s: sorted(set(s))),
                     owners=("race_county_owner", lambda s: sorted(set(x for x in s if x))))
                .reset_index())
    # County-level and statewide/district races list "<COUNTY> COUNTY" as the entity, so it differs by
    # county; every non-county entity (city, town, fire district) must be one jurisdiction per race.
    non_county = ~races["entity"].str.upper().str.endswith(" COUNTY")
    assert (races.loc[non_county, "n_entities"] == 1).all(), "a local race_number spans different entities"
    races["is_measure"] = races["options"].map(is_measure)
    races["contest_id"] = [base_contest_id(r.desc, r.entity, r.fips, year, r.is_measure)
                           for r in races.itertuples()]
    dupe_ids = races["contest_id"].duplicated(keep=False)      # make collisions unique via race_number
    races.loc[dupe_ids, "contest_id"] += "-" + races.loc[dupe_ids, "race_number"]
    assert races["contest_id"].is_unique

    # nonpartisan in Oklahoma: judges, retention, municipal and special-district races, ballot measures
    def is_nonpartisan(r) -> bool:
        d, e = norm(r.desc).upper(), norm(r.entity).upper()
        local = not e.endswith(" COUNTY")
        return r.is_measure or "JUDGE" in d or "COURT" in d or local

    races["nonpartisan"] = [is_nonpartisan(r) for r in races.itertuples()]
    races["office"] = [("Ballot measure" if r.is_measure else norm(r.desc)) for r in races.itertuples()]
    rmap = races.set_index("race_number")

    # ---- contest table -----------------------------------------------------------------
    c = raw.copy()
    c["election_date"] = election_date
    c["state"] = STATE
    c["county_name"] = c["county"].map(lambda k: COUNTIES[k][0])
    c["county_fips"] = c["county"].map(lambda k: COUNTIES[k][1])
    c["office"] = c["race_number"].map(rmap["office"])
    c["contest_id"] = c["race_number"].map(rmap["contest_id"])
    c["candidate"] = c["cand_name"]
    # party: source code verbatim (REP/DEM/IND/LIB); blank source on a nonpartisan office or
    # ballot option -> "N/A"; blank on a partisan office would stay blank (unknown).
    np_flag = c["race_number"].map(rmap["nonpartisan"])
    c["party"] = c["cand_party"].where(c["cand_party"] != "", other=pd.NA)
    c["party"] = c["party"].fillna(pd.Series(["N/A"] * len(c), index=c.index).where(np_flag, ""))
    c["votes"] = num["cand_tot_votes"].astype("Int64")      # source total; components not added again
    c["_rn"] = pd.to_numeric(c["race_number"])
    c["_cn"] = pd.to_numeric(c["cand_number"])
    contest = (c.sort_values(["_rn", "county_name", "_cn"], kind="stable")[CONTEST_COLS]
                .reset_index(drop=True))
    unknown_party = int(((contest["party"] == "") & ~c.sort_values(["_rn", "county_name", "_cn"],
                         kind="stable")["race_number"].map(rmap["nonpartisan"]).reset_index(drop=True)).sum())

    # ---- county table --------------------------------------------------------------------
    county = pd.DataFrame({
        "election_date": election_date, "state": STATE,
        "county_name": [v[0] for v in COUNTIES.values()],
        "county_fips": [v[1] for v in COUNTIES.values()],
        "ballots_cast": "", "registered_voters": ""})
    county = county[county["county_name"].isin(contest["county_name"])]
    if a.turnout:
        t = pd.read_csv(a.turnout, dtype=str, keep_default_na=False).set_index("county_name")
        for col in ("ballots_cast", "registered_voters"):
            county[col] = county["county_name"].map(t[col]).fillna("")
    county = county[COUNTY_COLS].sort_values("county_fips").reset_index(drop=True)

    # ---- reference table of contests ------------------------------------------------------
    ref = races.assign(
        n_counties=races["counties"].map(len),
        counties_covered=races["counties"].map(lambda l: "; ".join(COUNTIES[k][0] for k in l)),
        county_owner=races["owners"].map(lambda l: "; ".join(COUNTIES[k][0] for k in l)),
        scope=lambda d: d["n_counties"].map(lambda n: "all 77 counties" if n == len(COUNTIES) else
                                            "single county" if n == 1 else f"{n} counties (part of each)"),
        source_description=races["desc"].map(norm),
        jurisdiction=races["entity"],
    )[["contest_id", "race_number", "office", "source_description", "jurisdiction",
       "scope", "n_counties", "counties_covered", "county_owner"]]
    ref = ref.rename(columns={"race_number": "source_race_number"}).sort_values("contest_id")

    contest.to_csv(out / "contest_table.csv", index=False)
    county.to_csv(out / "county_table.csv", index=False)
    ref.to_csv(out / "contest_reference.csv", index=False)

    zero_rows = contest.groupby(["contest_id", "county_name"])["votes"].sum()
    zero_list = [f"{k[1]} in {k[0]}" for k, v in zero_rows.items() if v == 0]
    multi = ref[ref["n_counties"].between(2, len(COUNTIES) - 1)]
    notes = [
        f"Source: {Path(a.csv).name} (Oklahoma county results, election date {election_date}). "
        "Already one row per county-race-candidate/option; state OK is inferred from the county names.",
        "county_fips: derived from county name (40 + 3-digit county code); the file has no FIPS column.",
        "ballots_cast / registered_voters: NOT in the results file, left blank. Ballots were not "
        "estimated by adding candidate votes. Fill via --turnout and record the source's definition "
        "(ballots cast / accepted / counted; registration definition) here.",
        "votes: cand_tot_votes. The absentee/mail, early and election-day columns are its disjoint "
        f"components and were not added again; they sum to the total in every row ({comp_bad} mismatches).",
        f"Missing/non-numeric vote cells: {missing}; negative: {negative}; duplicate county-race-candidate rows: {dups}; "
        f"rows where precincts reporting < total precincts: {partial}.",
        "party: source code kept verbatim (REP, DEM, IND, LIB). Blank source party on ballot options "
        "(YES/NO) and on judicial, municipal and special-district contests is written as N/A "
        "(nonpartisan); this is an inference from office type, not a source label. "
        f"Blank-party rows left as unknown on partisan offices: {unknown_party}.",
        "No write-in aggregate lines appear in this file, so none are included.",
        "Contest IDs: statewide/district IDs use the usual codes (GOV, LTGOV, AG, TREAS, SPI, LABOR, INS, "
        "CORPCOMM, USS, USH-n, STS-n, STH-n, DJ-district-office, ADJ-county, SQ-n); county offices and "
        "measures are 2026-OK-county-<3-digit county FIPS>-...; city/town/fire-district contests use the "
        "jurisdiction slug. The same ID is used on every county row of the same source race_number; "
        "see contest_reference.csv for each ID's source number, description and geographic scope.",
        "Please confirm with the instructor: US Senate labeled 'regular' (the file has a single US Senate race); "
        "YES/NO contests for Supreme Court, Court of Criminal Appeals and Court of Civil Appeals seats are "
        "labeled '-retention' (inferred from the YES/NO options; the file names no judge).",
        "State questions and the statewide judicial retention contests appear in all 77 counties.",
        f"Geographic scope: {len(multi)} contests cover only part of each of 2+ counties (US House, state "
        "legislative, district judge, and some city contests); each county row is that county's portion of the "
        "district/jurisdiction. All other non-statewide contests are single-county. Votes for different "
        "offices must not be added as if they were distinct voters.",
        "Zero-vote county rows kept as reported (all options 0): " + ("; ".join(zero_list) or "none"),
        "race_county_owner is not a column in the output; it is listed in contest_reference.csv (county_owner).",
        "Results are as reported in the file; confirm against certified results.",
    ]
    (out / "notes.txt").write_text("\n".join(f"- {n}" for n in notes) + "\n")
    print(f"contest rows: {len(contest)}, counties: {len(county)}, contests: {len(ref)}")


if __name__ == "__main__":
    main()
