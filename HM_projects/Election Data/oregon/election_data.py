#!/usr/bin/env python3
"""
Pandas version: Oregon SOS "Statewide" results workbook -> class tables.

  county_table.csv:  election_date,state,county_name,county_fips,ballots_cast,registered_voters
  contest_table.csv: election_date,state,county_name,county_fips,office,contest_id,candidate,party,votes
  notes.txt

Usage:
  python build_tables_pandas.py Statewide.xlsx --statewide-csv Statewide.csv
                                [--outdir out] [--election-date 2026-11-03]
                                [--turnout turnout.csv]

Inputs:
  xlsx            county-level results, one sheet per contest (sheet name starts with ContestID)
  --statewide-csv statewide results with NominatingParty per candidate; supplies the
                  `party` column and is used to cross-check county sums against statewide totals
  --turnout       optional CSV: county_name,ballots_cast,registered_voters (official county-wide figures)
"""
import argparse, re, sys
from pathlib import Path
import pandas as pd

STATE = "OR"

# Oregon county FIPS, keyed by name (the sheet's CountyID is Oregon's internal code, not FIPS).
FIPS = {
    "Baker": "41001", "Benton": "41003", "Clackamas": "41005", "Clatsop": "41007",
    "Columbia": "41009", "Coos": "41011", "Crook": "41013", "Curry": "41015",
    "Deschutes": "41017", "Douglas": "41019", "Gilliam": "41021", "Grant": "41023",
    "Harney": "41025", "Hood River": "41027", "Jackson": "41029", "Jefferson": "41031",
    "Josephine": "41033", "Klamath": "41035", "Lake": "41037", "Lane": "41039",
    "Lincoln": "41041", "Linn": "41043", "Malheur": "41045", "Marion": "41047",
    "Morrow": "41049", "Multnomah": "41051", "Polk": "41053", "Sherman": "41055",
    "Tillamook": "41057", "Umatilla": "41059", "Union": "41061", "Wallowa": "41063",
    "Wasco": "41065", "Washington": "41067", "Wheeler": "41069", "Yamhill": "41071",
}

CONTEST_COLS = ["election_date", "state", "county_name", "county_fips",
                "office", "contest_id", "candidate", "party", "votes"]
COUNTY_COLS = ["election_date", "state", "county_name", "county_fips",
               "ballots_cast", "registered_voters"]


def make_contest_id(office: str, year: str) -> str:
    o = office.lower()
    if "senator" in o:
        return f"{year}-{STATE}-USS-regular"
    m = re.search(r"representative.*?(\d+)", o)
    if m:
        return f"{year}-{STATE}-USH-{int(m.group(1))}"
    slug = re.sub(r"[^A-Za-z0-9]+", "-", office).strip("-")
    print(f"WARNING: ambiguous office '{office}' -> {slug}; confirm label", file=sys.stderr)
    return f"{year}-{STATE}-{slug}"


def read_statewide_csv(path: str) -> pd.DataFrame:
    """Statewide.csv has a trailing comma on every row (16 fields vs 15 headers), so give
    the columns explicit names instead of letting pandas shift them into the index."""
    cols = pd.read_csv(path, nrows=0).columns.tolist()
    df = pd.read_csv(path, header=0, names=cols + ["_extra"], dtype=str,
                     keep_default_na=False)
    df["CandidateName"] = df["CandidateName"].str.strip()
    df["NominatingParty"] = df["NominatingParty"].str.strip()
    df["CandidateVotes"] = pd.to_numeric(df["CandidateVotes"], errors="coerce").astype("Int64")
    return df[["ContestID", "CandidateName", "NominatingParty", "CandidateVotes"]]


def read_contest(sheet_name: str, raw: pd.DataFrame, election_date: str) -> pd.DataFrame:
    """Turn one raw sheet (read with header=None) into a long contest dataframe."""
    hdr_i = raw.index[raw[1] == "County"][0]
    office = str(raw.loc[hdr_i, 0]).strip()
    cand_cols = [c for c in raw.columns[3:] if pd.notna(raw.loc[hdr_i, c])]
    cand_names = {c: str(raw.loc[hdr_i, c]).strip() for c in cand_cols}

    body = raw.loc[hdr_i + 1:, [1] + cand_cols].rename(columns={1: "county_name"})
    body = body.rename(columns=cand_names)
    body["county_name"] = body["county_name"].astype("string").str.strip()
    body = body[body["county_name"].notna()]
    body = body[body["county_name"].str.upper() != "TOTALS"]  # source totals dropped

    # melt is candidate-major; a stable sort on the original row keeps county-then-candidate order
    long = (body.reset_index().melt(id_vars=["index", "county_name"],
                                    var_name="candidate", value_name="votes")
                .sort_values("index", kind="stable").drop(columns="index"))
    long["votes"] = pd.to_numeric(long["votes"], errors="coerce").astype("Int64")
    long["office"] = office
    long["source_contest_id"] = sheet_name.split()[0]   # e.g. 300038695
    long["contest_id"] = make_contest_id(office, election_date[:4])
    return long


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--election-date", default="2026-11-03")
    ap.add_argument("--turnout")
    ap.add_argument("--statewide-csv", required=True)
    a = ap.parse_args()

    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)

    sheets = pd.read_excel(a.xlsx, sheet_name=None, header=None)
    contest = pd.concat([read_contest(n, df, a.election_date) for n, df in sheets.items()],
                        ignore_index=True)

    contest["election_date"] = a.election_date
    contest["state"] = STATE
    contest["county_fips"] = contest["county_name"].map(FIPS).fillna("")
    for c in contest.loc[contest["county_fips"] == "", "county_name"].unique():
        print(f"WARNING: no FIPS for county '{c}'", file=sys.stderr)

    # Party: the source's NominatingParty label from Statewide.csv, matched on
    # (ContestID from the sheet name, candidate name). Labels are kept verbatim
    # (e.g. "Democrat, Working Families"). Write-in has no label in the source -> blank.
    sw = read_statewide_csv(a.statewide_csv)
    pmap = sw.set_index(["ContestID", "CandidateName"])["NominatingParty"]
    keys = pd.MultiIndex.from_frame(contest[["source_contest_id", "candidate"]])
    contest["party"] = pmap.reindex(keys).to_numpy()
    contest["party"] = contest["party"].fillna("")
    unmatched = contest.loc[~keys.isin(pmap.index), "candidate"].unique()
    if len(unmatched):
        print(f"WARNING: candidates not found in {a.statewide_csv}: {list(unmatched)}",
              file=sys.stderr)

    # Cross-check: county rows should add up to the statewide CSV total for each candidate.
    chk = (contest.groupby(["source_contest_id", "candidate"])["votes"].sum()
                  .rename("county_sum").reset_index()
                  .merge(sw, left_on=["source_contest_id", "candidate"],
                         right_on=["ContestID", "CandidateName"], how="left"))
    bad = chk[chk["county_sum"] != chk["CandidateVotes"]]
    mismatches = [f"{r.source_contest_id} {r.candidate}: counties {r.county_sum} vs statewide {r.CandidateVotes}"
                  for r in bad.itertuples()]
    for m in mismatches:
        print("WARNING: total mismatch -", m, file=sys.stderr)

    contest = contest[CONTEST_COLS]

    # County table: one row per county; ballots/registration blank unless supplied.
    county = (contest[["election_date", "state", "county_name", "county_fips"]]
              .drop_duplicates().sort_values("county_name").reset_index(drop=True))
    county["ballots_cast"] = ""
    county["registered_voters"] = ""
    if a.turnout:
        t = pd.read_csv(a.turnout, dtype=str).set_index("county_name")
        for col in ("ballots_cast", "registered_voters"):
            county[col] = county["county_name"].map(t[col]).fillna("")
    county = county[COUNTY_COLS]

    # Zero-vote county/contest combinations, for the notes.
    sums = contest.groupby(["contest_id", "county_name"])["votes"].sum()
    zeros = [f"{c} in {k}" for (k, c), v in sums.items() if v == 0]

    contest.to_csv(out / "contest_table.csv", index=False)
    county.to_csv(out / "county_table.csv", index=False)

    notes = [
        f"Source: {Path(a.xlsx).name} - Oregon unofficial general election results, "
        f"downloaded 11/9/2026 (per sheet header). Election date {a.election_date} "
        "is supplied by this script, not stated in the workbook.",
        "county_fips: derived from county name (41 + 3-digit county code). The sheet's "
        "CountyID column is the Oregon SOS internal code, not FIPS, and was not used.",
        "ballots_cast / registered_voters: NOT in the workbook, left blank. Ballots were not "
        "estimated by summing candidate votes. Fill via --turnout from the official county "
        "source and record its definition (cast / accepted / counted; registration definition) here.",
        "party: taken verbatim from NominatingParty in Statewide.csv (matched on ContestID + "
        "candidate name). Multi-party nominations are kept as the source writes them, e.g. "
        "'Democrat, Working Families'. The aggregate Write-in line has no label in the source, "
        "so its party is blank (unknown).",
        "Cross-check: county rows summed per candidate "
        + ("match the Statewide.csv totals for every candidate." if not mismatches
           else "DO NOT match Statewide.csv for: " + "; ".join(mismatches)),
        "TOTALS rows in each sheet were dropped (source totals; components are kept, never both).",
        "Contests: US Senator (2026-OR-USS-regular) and US House districts 1-6 (2026-OR-USH-N). "
        "Whether the Senate seat is regular vs special should be confirmed.",
        "Geographic scope: House contests cover only the portion of a county inside that "
        "district. Counties split across districts have separate rows per district; do not add "
        "different offices' votes together as distinct people.",
        "'Write-in' is the source's aggregate write-in line and is kept as a candidate row.",
        "Zero-vote rows kept as reported (all candidates 0); verify: " + "; ".join(zeros),
        "Very small counts (e.g. Jefferson in USH-5, Linn in USH-4) likely reflect tiny "
        "precinct slivers of a split county; kept as reported.",
        "Results are UNOFFICIAL (Statewide.csv PrecinctsReporting field reads 0/N for every contest); re-pull after certification.",
    ]
    (out / "notes.txt").write_text("\n".join(f"- {n}" for n in notes) + "\n")
    print(f"contest rows: {len(contest)}, counties: {len(county)}")


if __name__ == "__main__":
    main()