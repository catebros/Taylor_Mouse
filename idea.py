import streamlit as st
from newproject.trim import trim
from newproject.crop import crop

st.title('Cropping and Trimming')

with st.sidebar:
    st.header('Select')
    crop_selected = st.checkbox('Crop')
    trim_selected = st.checkbox('Trim')

uploaded_files = st.file_uploader("Choose a video", accept_multiple_files=True)

if crop_selected:
    crop()

if trim_selected:
    trim()

