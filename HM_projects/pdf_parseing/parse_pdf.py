import pdfplumber
import pandas as pd
import re


def fetchPDF(filepath):
    pdf = pdfplumber.open(filepath)
    pdfList = []
    for i in range(len(pdf.pages)):
        page = pdf.pages[i]
        page_text = page.extract_text().split('\n')
        pdfList.append(page_text)
    pdf.close()
    return pdfList

#these are regx expressions
TABLE_HEADER_RE = re.compile(r'^Table\s+\d+\.\s*(.+)$')
NUMERIC_TOKEN_RE = re.compile(r'-?\d+\.?\d*%|\b\d{4}\b')  # percentages or 4-digit numbers/years 
def is_table_row(line, min_numeric_tokens=2):
    return len(NUMERIC_TOKEN_RE.findall(line)) >= min_numeric_tokens

def extract_tables_from_text(all_lines):
    tables = {}
    current_title = None
    current_rows = []

    for line in all_lines:
        line = line.strip()
        if not line:
            continue

        header_match = TABLE_HEADER_RE.match(line)
        if header_match:
            if current_title:
                tables[current_title] = current_rows
            current_title = line
            current_rows = []
            continue

        if current_title:
            if is_table_row(line):
                current_rows.append(line)
            else:
                tables[current_title] = current_rows
                current_title = None
                current_rows = []

    if current_title:
        tables[current_title] = current_rows

    return tables

def dataFrameConstructer(rows):
    def split_row(line):
        values = NUMERIC_TOKEN_RE.findall(line)
        label = NUMERIC_TOKEN_RE.sub('', line).strip()
        return [label] + values

    def clean_cell(cell):
        return cell.replace('\r', '').replace('\n', ' ').strip()

    header_cells = split_row(rows[0])
    data = [split_row(r) for r in rows[1:]]

    max_cols = max(len(header_cells), max((len(r) for r in data), default=0))
    header_cells += [''] * (max_cols - len(header_cells))
    data = [r + [''] * (max_cols - len(r)) for r in data]

    header_cells = [clean_cell(c) for c in header_cells]
    data = [[clean_cell(c) for c in row] for row in data]

    df = pd.DataFrame(data, columns=header_cells)
    df = df.replace('', pd.NA)
    df = df.dropna(axis=0, how='all')
    df = df.dropna(axis=1, how='all')

    if df.empty or df.columns.empty:
       # print(f"WARNING: skipping table that became empty after cleaning — header was: {rows[0]!r}") no longer need to print since this was for debug
        return None

    label_col = df.columns[0]
    df[label_col] = df[label_col].ffill()

    for col in df.columns[1:]:
        cleaned = df[col].astype(str).str.replace('%', '', regex=False) \
                                      .str.replace('$', '', regex=False) \
                                      .str.replace(',', '', regex=False)
        converted = pd.to_numeric(cleaned, errors='coerce')
        if converted.notna().sum() >= len(converted) * 0.5:
            df[col] = converted

    return df

def main():
    pdf = fetchPDF("/Users/elliotbangerter/Data Wrangeling /HM_projects/pdf_parseing/2025GraduationRates.pdf")
    

    all_lines = [line for page in pdf for line in page]
    tables_dict = extract_tables_from_text(all_lines)

    dataframes = {
        title: dataFrameConstructer(rows)
        for title, rows in tables_dict.items()
    }
    dataframes = {title: df for title, df in dataframes.items() if df is not None}
    
    with open("all_tables_output.csv", "w", newline='') as f:
        for title, df in dataframes.items():
            f.write(f"{title}\n")
            df.to_csv(f, index=False)
            f.write("\n")  # blank line between tables

main()