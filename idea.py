import streamlit as st
import tempfile
import os
from trim import trim
from crop import crop

st.set_page_config(page_title="Video Processing", layout="wide")

st.title('Video Processing')

downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
st.info(f"All processed videos will be saved to your Downloads folder: {downloads_path}")

col1, col2 = st.columns([1, 2])

with col1:
    st.header('Processing Options')
    crop_selected = st.checkbox('Crop Videos')
    trim_selected = st.checkbox('Trim Videos')

with col2:
    st.header('Upload Videos')
    uploaded_files = st.file_uploader(
        "Choose video files", 
        accept_multiple_files=True,
        type=['mp4', 'avi', 'mov', 'mkv', 'wmv']
    )

if uploaded_files:
    st.header(f'Uploaded Files ({len(uploaded_files)})')

    temp_dir = tempfile.mkdtemp()
    temp_file_paths = []
    
    try:
        for uploaded_file in uploaded_files:
            temp_file_path = os.path.join(temp_dir, uploaded_file.name)
            with open(temp_file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            temp_file_paths.append(temp_file_path)
        
        for i, (file, temp_path) in enumerate(zip(uploaded_files, temp_file_paths), 1):
            file_size = len(file.getbuffer()) / (1024 * 1024)
            
            try:
                import ffmpeg
                probe = ffmpeg.probe(temp_path)
                duration = float(probe['format']['duration'])
                duration_str = f"{duration:.1f}s"
            except:
                duration_str = "Unknown"
            
            col_a, col_b, col_c = st.columns([3, 1, 1])
            with col_a:
                st.write(f"{i}. {file.name}")
            with col_b:
                st.write(f"{file_size:.1f} MB")
            with col_c:
                st.write(duration_str)
    
        if crop_selected or trim_selected:
            temp_dir = tempfile.mkdtemp()
            temp_file_paths = []
            
            try:
                with st.spinner("Preparing files for processing..."):
                    for uploaded_file in uploaded_files:
                        temp_file_path = os.path.join(temp_dir, uploaded_file.name)
                        
                        with open(temp_file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        temp_file_paths.append(temp_file_path)
                
                if crop_selected:
                    crop(temp_file_paths)

                if trim_selected:
                    trim(temp_file_paths)
                
            finally:
                for temp_file_path in temp_file_paths:
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                os.rmdir(temp_dir)
        else:
            st.warning("Please select at least one processing option (Crop or Trim)")
    
    finally:
        for temp_file_path in temp_file_paths:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
else:
    st.info("Upload video files to begin processing")