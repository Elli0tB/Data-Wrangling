import pdfplumber


def fetchPDF(filepath):
    
    pdf =  pdfplumber.open(filepath)
    pdfList = []
    table_settings={ 
        "vertical_strategy": "text", 
        "horizontal_strategy": "text", 
        "intersection_tolerance": 10,
        "intersection_x_tolerance": 10,
        "intersection_y_tolerance": 10,
        "text_tolerance": 10,
        "text_x_tolerance": 10,
        "text_y_tolerance": 10,
        }
    #for i in range((len(pdf.pages))):
    page = pdf.pages[4]
    # for c in page.chars:
    #     print(c["text"], c["fontname"], c["x0"], c["top"])
    page_table_data = page.extract_tables(table_settings=table_settings)
    pdfList.append(page_table_data)
    print(pdfList)
    print(page.extract_text())
    im = page.to_image(resolution=150)
    im.debug_tablefinder(table_settings).show()

    

    
def main():
    pdf = fetchPDF("./2025GraduationRates.pdf")



main()