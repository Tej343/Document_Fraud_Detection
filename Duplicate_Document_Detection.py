import streamlit as st
import hashlib
import os
import fitz  # PyMuPDF
import pytesseract
import cv2
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------- Utilities ----------

def compute_hash(file_path, algo='sha256'):
    hash_func = hashlib.new(algo)
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hash_func.update(chunk)
    return hash_func.hexdigest()

def extract_text_from_pdf(file_path):
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

def extract_text_from_image(file_path):
    try:
        img = cv2.imread(file_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        gray = cv2.medianBlur(gray, 3)
        return pytesseract.image_to_string(gray)
    except Exception as e:
        return ""

def extract_text(file_path):
    ext = os.path.splitext(file_path)[-1].lower()
    try:
        if ext == '.pdf':
            return extract_text_from_pdf(file_path)
        elif ext in ['.jpg', '.jpeg', '.png']:
            return extract_text_from_image(file_path)
        else:
            return ""
    except Exception:
        return ""

def compute_cosine_similarity(text1, text2):
    # Clean and check for empty or meaningless text
    text1 = text1.strip()
    text2 = text2.strip()
    if not text1 or not text2:
        return 0.0  # Avoid TF-IDF error
    try:
        vectorizer = TfidfVectorizer()
        vectors = vectorizer.fit_transform([text1, text2])
        return cosine_similarity(vectors[0], vectors[1])[0][0]
    except ValueError:
        return 0.0  # In case of stopword-only documents or other TF-IDF issues

# ---------- Streamlit UI ----------

st.set_page_config(layout="wide")
# st.title("📄 Duplicate Document Checker (Hash + Content Based)")
st.title("📄 Duplicate Document Checker")

col1, col2 = st.columns(2)

# Left side: Source documents
with col1:
    st.header("📁 Source Documents")
    source_folder = st.text_input("Select folder path for source files")
    source_files = []
    if source_folder and os.path.isdir(source_folder):
        source_files = [
            os.path.join(source_folder, f)
            for f in os.listdir(source_folder)
            if f.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg'))
        ]
        st.write(f"Found {len(source_files)} files.")

# Right side: Target file
with col2:
    st.header("🎯 Target File")
    target_file = st.file_uploader("Upload the file to check", type=["pdf", "png", "jpg", "jpeg"])
    if target_file:
        # Save uploaded file temporarily
        target_path = os.path.join("temp_uploaded", target_file.name)
        os.makedirs("temp_uploaded", exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(target_file.read())

# ---------- Processing ----------

if st.button("🔍 Check for Duplicates"):
    if not source_files or not target_file:
        st.warning("Please select both source files and a target file.")
    else:
        results = []
        found_exact_duplicate = False

        # Precompute for target file
        target_hash = compute_hash(target_path)
        target_text = extract_text(target_path)

        for file_path in source_files:
            source_hash = compute_hash(file_path)
            source_text = extract_text(file_path)
            similarity_score = compute_cosine_similarity(source_text, target_text)

            is_exact = source_hash == target_hash
            if is_exact:
                found_exact_duplicate = True
                st.markdown(
                    f"<div style='background-color:#ffcccc;padding:15px;border-radius:10px;'>"
                    f"<h4>⚠️ Exact Duplicate Found: <code>{os.path.basename(file_path)}</code></h4>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            results.append({
                "Source File": os.path.basename(file_path),
                "Hash Match": is_exact,
                "Cosine Similarity": round(similarity_score * 100, 2),
                "Source Hash": source_hash,
                "Target Hash": target_hash,
            })

        df = pd.DataFrame(results)

        # Find the most similar document
        if not df.empty:
            best_match = df.sort_values(by="Cosine Similarity", ascending=False).iloc[0]
            file_name = best_match["Source File"]
            score = best_match["Cosine Similarity"]

            if score < 50:
                st.markdown(
                    f"<div style='background-color:#e7f3fe;padding:15px;border-radius:10px;'>"
                    f"<h4>🟢 No similarity issues found with <code>{file_name}</code> (Score: {score}%)</h4>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            elif 50 <= score < 70:
                st.markdown(
                    f"<div style='background-color:#fff3cd;padding:15px;border-radius:10px;'>"
                    f"<h4>🟠 Possible Related Document: <code>{file_name}</code> (Score: {score}%)</h4>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"<div style='background-color:#f8d7da;padding:15px;border-radius:10px;'>"
                    f"<h4>🔴 <strong>Potential Duplicate!</strong> Found: <code>{file_name}</code> (Score: {score}%)</h4>"
                    f"</div>",
                    unsafe_allow_html=True
                )

        df.rename(columns={'Cosine Similarity': 'Match Score', 'Hash Match': 'Exact Match'}, inplace=True)
        df = df[['Source File', 'Exact Match', 'Match Score']]
        df = df.sort_values(by='Match Score', ascending=False)

        # Optional: Show full results below
        with st.expander("📊 Full Comparison Table"):
            st.dataframe(df)

        # Downloadable CSV
        csv = df.to_csv(index=False)
        st.download_button("📥 Download Results as CSV", csv, "results.csv", "text/csv")
