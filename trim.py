import streamlit as st
import os
import ffmpeg
import math

def trim(uploaded_files):
    PATHS = ['d:\Videos\Exp7_males_early_2hstress\Hour1\Exp7_1_cam1_H1_mouse02.mp4',
         'd:\Videos\Exp7_males_early_2hstress\Hour1\Exp7_1_cam2_H1_mouse03.mp4']
    
    for file in uploaded_files:
        #  max chunk value min video length
        ...

    CHUNK_DURATION = st.sidebar.number_input("Chunk duration (s):") #max_value
    
    OUTPUT_DIR = 'Experiment7_Trimmed'
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for video_path in PATHS:
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        video_output_dir = os.path.join(OUTPUT_DIR, video_name)
        os.makedirs(video_output_dir, exist_ok=True)

        probe = ffmpeg.probe(video_path)
        print("probe")
        duration = float(probe['format']['duration'])
        number_chunks = math.ceil(duration/CHUNK_DURATION)

        for i in range(number_chunks):
            start = i * CHUNK_DURATION
            output_file = os.path.join(video_output_dir, f'{video_name}_part_{i+1}.mp4')
            (
                ffmpeg
                .input(video_path, ss = start, t = CHUNK_DURATION)
                .output(output_file)
                .overwrite_output()
                .run()
            )

            print(f'--------------------Chunk {i+1}/{number_chunks} done!-------------------------')