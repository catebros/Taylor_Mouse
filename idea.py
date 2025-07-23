import streamlit as st
import tempfile
import os
from trim import trim
from crop import crop
from crop_trim import crop_trim
import ffmpeg

st.set_page_config(page_title="Video Processing", layout="wide")

st.title('Video Processing')

col1, col2 = st.columns([1, 2])

with col1:
    st.header('Processing Options')
    crop_trim_selected = st.radio('Processing Options', ['Crop', 'Trim', 'Crop and Trim'])

with col2:
    st.header('Upload Videos')
    uploaded_files = st.file_uploader(
        "Choose video files", 
        accept_multiple_files=True,
        type=['mp4']
    )

if uploaded_files:
    temp_dir = tempfile.mkdtemp()
    temp_file_paths = []

    try:
        for uploaded_file in uploaded_files:
            temp_file_path = os.path.join(temp_dir, uploaded_file.name)
            with open(temp_file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            temp_file_paths.append(temp_file_path)

        if crop_trim_selected == 'Crop':
            crop(temp_file_paths)
        elif crop_trim_selected == 'Trim':
            trim(temp_file_paths)
        elif crop_trim_selected == 'Crop and Trim':
            crop_trim(temp_file_paths)
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
