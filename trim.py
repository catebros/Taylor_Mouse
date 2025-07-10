import streamlit as st
import os
import ffmpeg
import math

def trim(temp_file_paths): 
    if not temp_file_paths:
        st.error("No files provided")
        return
    
    try:
        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
        
        st.info("Trimmed videos will be saved to your Downloads folder")
        
        durations = []
        
        for video in temp_file_paths:
            probe = ffmpeg.probe(video)
            duration = float(probe['format']['duration'])
            durations.append(duration)
        
        min_length = min(durations)

        st.sidebar.header('Trim Settings')  
        CHUNK_DURATION = st.sidebar.slider(
            "Chunk duration (seconds)", 
            min_value=1.0, 
            max_value=float(min_length), 
            value=min(5.0, float(min_length)), 
            step=0.5,
        )

        st.sidebar.header('Output Settings')
        OUTPUT_DIR = st.sidebar.text_input("Folder name in Downloads", "Trimmed_Videos")
        full_output_path = os.path.join(downloads_path, OUTPUT_DIR)
        os.makedirs(full_output_path, exist_ok=True)


        if st.sidebar.button("Start Trimming Videos", type="primary"):
            st.subheader("Trimming Process")
            
            for video_idx, video_path in enumerate(temp_file_paths):
                video_name = os.path.splitext(os.path.basename(video_path))[0]
                video_output_dir = os.path.join(full_output_path, video_name)
                os.makedirs(video_output_dir, exist_ok=True)

                probe = ffmpeg.probe(video_path)
                duration = float(probe['format']['duration'])
                number_chunks = math.ceil(duration / CHUNK_DURATION)
                

                st.write(f"**Video {video_idx + 1}/{len(temp_file_paths)}: {video_name}**")
                st.write(f"Duration: {duration:.1f} seconds -> Creating {number_chunks} chunks of {CHUNK_DURATION}s each")
                
                video_progress = st.progress(0)
                chunk_status = st.empty()

                for i in range(number_chunks):
                    start = i * CHUNK_DURATION
                    end_time = min(start + CHUNK_DURATION, duration)
                    output_file = os.path.join(video_output_dir, f'{video_name}_part_{i+1}.mp4')
                    
                    chunk_status.info(f"Processing chunk {i+1}/{number_chunks} (from {start:.1f}s to {end_time:.1f}s)")
                    
                    (
                        ffmpeg
                        .input(video_path, ss=start, t=CHUNK_DURATION)
                        .output(output_file)
                        .overwrite_output()
                        .run()
                    )

                    progress_value = (i + 1) / number_chunks
                    video_progress.progress(progress_value)
                
                chunk_status.success(f'Completed {video_name} - {number_chunks} chunks saved to Downloads/{OUTPUT_DIR}/{video_name}/')
                st.write("---")
            
            st.success(f"All videos trimmed successfully! Check your Downloads folder: {full_output_path}")
            
    except Exception as e:
        st.error(f"Error processing videos: {str(e)}")