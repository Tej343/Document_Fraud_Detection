import streamlit as st
import os
import json
import pandas as pd
from PyPDF2 import PdfReader
from datetime import datetime

# Define suspicious keywords
SUSPICIOUS_KEYWORDS = [
    'microsoft word', 'libreoffice', 'cutepdf',
    'openoffice', 'pdf creator', 'ilovepdf', 'smallpdf', 'pdfescape',
    'wondershare', 'foxit', 'nitro', 'sejda', 'online2pdf', 'Microsoft: Print To PDF', 'Adobe' #'ghostscript',
]

# Function to clean non-ASCII characters
def remove_non_ascii(text):
    """Remove non-ASCII characters from a string."""
    return text.encode('ascii', 'ignore').decode('ascii')

def clean_pdf_date(date_str):
    """Convert PDF date string to datetime."""
    try:
        if date_str.startswith("D:"):
            date_str = date_str[2:]
        return datetime.strptime(date_str[:14], '%Y%m%d%H%M%S')
    except:
        return None

# Function to analyze a PDF file
def analyze_pdf(file_path):
    try:
        reader = PdfReader(file_path)
        meta = reader.metadata

        # Prepare result dictionary
        result = {
            "File Name": os.path.basename(file_path),
            "Edited": False,
            "Reasons": "",
            "Creation Date": "",
            "Modification Date": "",
            "Producer": meta.get('/Producer', '') if meta else '',
            "Creator": meta.get('/Creator', '') if meta else '',
            "Title": meta.get('/Title', '') if meta else '',
            "Full Metadata": json.dumps(dict(meta), indent=2) if meta else "{}"
        }

        # Parse dates
        creation_date = clean_pdf_date(meta.get('/CreationDate', '')) if meta else None
        mod_date = clean_pdf_date(meta.get('/ModDate', '')) if meta else None

        if creation_date:
            result["Creation Date"] = creation_date.strftime("%Y-%m-%d %H:%M:%S")
        if mod_date:
            result["Modification Date"] = mod_date.strftime("%Y-%m-%d %H:%M:%S")

        # Start collecting reasons
        reasons = []

        # 1. Check if ModDate is later than CreationDate
        if creation_date and mod_date and mod_date > creation_date:
            result["Edited"] = True
            reasons.append("Modification date is later than creation date.")

        # 2. Check for suspicious software
        for key in ['/Producer', '/Creator', '/Title']:
            val = meta.get(key, '') if meta else ''
            val = remove_non_ascii(val)  # Clean non-ASCII characters
            for word in SUSPICIOUS_KEYWORDS:
                if word.lower() in val.lower():
                    result["Edited"] = True
                    reasons.append(f"Suspicious keyword '{word}' found in {key}: {val}")

        result["Reasons"] = "\n".join(reasons)

        return result

    except Exception as e:
        return {
            "File Name": os.path.basename(file_path),
            "Edited": None,
            "Reasons": f"Error: {str(e)}",
            "Creation Date": "",
            "Modification Date": "",
            "Producer": "",
            "Creator": "",
            "Title": "",
            "Full Metadata": "{}"
        }

# Streamlit UI
def main():
    st.title("Document Tamper Check")

    # Upload PDF files
    uploaded_files = st.file_uploader("Upload PDF files", type="pdf", accept_multiple_files=True)

    if uploaded_files:
        results = []

        for pdf in uploaded_files:
            st.write(f"Analyzing: {pdf.name}")
            # Save uploaded file temporarily
            with open(f"temp_{pdf.name}", "wb") as f:
                f.write(pdf.getbuffer())

            # Analyze the file
            result = analyze_pdf(f"temp_{pdf.name}")
            results.append(result)

            # Remove temporary file after processing
            os.remove(f"temp_{pdf.name}")

        # Create a DataFrame from the results
        df = pd.DataFrame(results)

        # Display results
        st.subheader("Analysis Results")
        st.write("Summary of PDF files processed:")

        # Display table
        # st.dataframe(df[['File Name', 'Edited', 'Creation Date', 'Modification Date', 'Reasons']])
        st.dataframe(df[['File Name', 'Edited']])

        # Provide download button for CSV
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="pdf_analysis_results.csv",
            mime="text/csv"
        )
    else:
        st.info("Please upload PDF files to start the analysis.")

if __name__ == "__main__":
    main()
