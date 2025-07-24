import streamlit as st
import os
import ffmpeg
import math
import zipfile

def hms_to_seconds(h, m, s):
    return h * 3600 + m * 60 + s

def seconds_to_hms(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02}:{m:02}:{s:02}"

def trim(temp_file_paths):
    if not temp_file_paths:
        st.error("No files provided")
        return

    try:
        ZIP_THRESHOLD_MB = 500 
        
        st.sidebar.title("Trimming Configuration")
        
        st.sidebar.header("1. Trimming Mode")
        trimming_mode = st.sidebar.radio(
            "How to apply trimming settings:",
            ["Same settings for all videos", "Individual settings per video"],
            index=1
        )

        video_names = [os.path.basename(p) for p in temp_file_paths]
        
        if trimming_mode == "Individual settings per video":
            st.sidebar.subheader("Video Selection")
            selected_idx = st.sidebar.selectbox("Select video to configure:", range(len(video_names)), format_func=lambda i: video_names[i])
            selected_name = video_names[selected_idx]
        else:
            selected_idx = 0
            selected_name = video_names[0]
            st.sidebar.info("Settings will be applied to all videos")
        
        selected_path = temp_file_paths[selected_idx]

        if "video_settings" not in st.session_state:
            st.session_state.video_settings = {}

        for path in temp_file_paths:
            name = os.path.basename(path)
            if name not in st.session_state.video_settings:
                try:
                    duration = float(ffmpeg.probe(path)['format']['duration'])
                except:
                    duration = 86400.0
                st.session_state.video_settings[name] = {
                    "duration": duration,
                    "start_h": 0,
                    "start_m": 0,
                    "start_s": 0,
                    "chunk_h": 0,
                    "chunk_m": 0,
                    "chunk_s": 0,
                }

        cfg = st.session_state.video_settings[selected_name]

        st.sidebar.subheader("Start Time (H:M:S)")
        col1, col2, col3 = st.sidebar.columns(3)
        with col1:
            start_h = st.number_input("H", 0, 23, cfg["start_h"], key=f"{selected_name}_sh", format="%d")
        with col2:
            start_m = st.number_input("M", 0, 59, cfg["start_m"], key=f"{selected_name}_sm", format="%d")
        with col3:
            start_s = st.number_input("S", 0, 59, cfg["start_s"], key=f"{selected_name}_ss", format="%d")

        st.sidebar.subheader("Chunk Duration (H:M:S)")
        col1, col2, col3 = st.sidebar.columns(3)
        with col1:
            chunk_h = st.number_input("H", 0, 24, cfg["chunk_h"], key=f"{selected_name}_ch", format="%d")
        with col2:
            chunk_m = st.number_input("M", 0, 59, cfg["chunk_m"], key=f"{selected_name}_cm", format="%d")
        with col3:
            chunk_s = st.number_input("S", 0, 59, cfg["chunk_s"], key=f"{selected_name}_cs", format="%d")

        # Change button label based on mode
        if trimming_mode == "Same settings for all videos":
            button_label = "Apply Settings to All Videos"
        else:
            button_label = f"Set Times for {selected_name}"

        if st.sidebar.button(button_label, type="secondary"):
            start_total = hms_to_seconds(start_h, start_m, start_s)
            chunk_total = hms_to_seconds(chunk_h, chunk_m, chunk_s)
            available_time = cfg["duration"] - start_total
            
            if chunk_total <= 0:
                st.sidebar.error("Chunk duration must be greater than 0!")
            elif start_total >= cfg["duration"]:
                st.sidebar.error("Start time exceeds video duration!")
            elif chunk_total > available_time:
                st.sidebar.error(f"Chunk duration ({seconds_to_hms(chunk_total)}) exceeds available time ({seconds_to_hms(available_time)})!")
            else:
                # Apply to current video first
                cfg["start_h"] = start_h
                cfg["start_m"] = start_m
                cfg["start_s"] = start_s
                cfg["chunk_h"] = chunk_h
                cfg["chunk_m"] = chunk_m
                cfg["chunk_s"] = chunk_s
                
                if trimming_mode == "Same settings for all videos":
                    # Apply to all videos
                    for path in temp_file_paths:
                        name = os.path.basename(path)
                        if name in st.session_state.video_settings:
                            st.session_state.video_settings[name]["start_h"] = start_h
                            st.session_state.video_settings[name]["start_m"] = start_m
                            st.session_state.video_settings[name]["start_s"] = start_s
                            st.session_state.video_settings[name]["chunk_h"] = chunk_h
                            st.session_state.video_settings[name]["chunk_m"] = chunk_m
                            st.session_state.video_settings[name]["chunk_s"] = chunk_s
                    st.sidebar.success("Settings applied to all videos!")
                else:
                    st.sidebar.success(f"Times set for {selected_name}!")

        st.sidebar.markdown("---")
        
        st.sidebar.header("2. Output Configuration")

        st.header("Video Trim Settings")
        table_data = []
        for path in temp_file_paths:
            name = os.path.basename(path)
            conf = st.session_state.video_settings.get(name, {})
            start = hms_to_seconds(conf.get("start_h", 0), conf.get("start_m", 0), conf.get("start_s", 0))
            chunk = hms_to_seconds(conf.get("chunk_h", 1), conf.get("chunk_m", 0), conf.get("chunk_s", 0))
            table_data.append({
                "Video Name": name,
                "Start Time": seconds_to_hms(start),
                "Chunk Duration": seconds_to_hms(chunk)
            })
        st.table(table_data)
        
        st.sidebar.subheader("Output Folder")
        output_base_path = st.sidebar.text_input("Full output folder path", os.path.join(os.path.expanduser("~"), "Videos", "Trimmed"))
        
        folder_exists = os.path.exists(output_base_path)
        if folder_exists:
            existing_files = []
            for root, dirs, files in os.walk(output_base_path):
                existing_files.extend([f for f in files if f.endswith('.mp4')])
            
            if existing_files:
                st.sidebar.warning(f"Folder exists with {len(existing_files)} files!")
                overwrite_option = st.sidebar.radio(
                    "What to do with existing files?",
                    ["Overwrite existing files", "Create new folder with timestamp"],
                    index=1
                )
            else:
                overwrite_option = "Overwrite existing files"
        else:
            overwrite_option = "Overwrite existing files"
        
        if overwrite_option == "Create new folder with timestamp" and folder_exists:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_output_path = f"{output_base_path}_{timestamp}"
            st.sidebar.info(f"Will create: {os.path.basename(final_output_path)}")
        else:
            final_output_path = output_base_path

        st.sidebar.subheader("File Naming")
        
        if "prefix_settings" not in st.session_state:
            st.session_state.prefix_settings = {}
        
        for path in temp_file_paths:
            video_name = os.path.basename(path)
            if video_name not in st.session_state.prefix_settings:
                default_prefix = video_name.split('_')[0] if '_' in video_name else os.path.splitext(video_name)[0]
                st.session_state.prefix_settings[video_name] = default_prefix
        
        st.sidebar.markdown("**Customize output prefixes:**")
        
        for path in temp_file_paths:
            video_name = os.path.basename(path)
            current_prefix = st.session_state.prefix_settings[video_name]
            
            new_prefix = st.sidebar.text_input(
                f"Prefix for {video_name}:",
                value=current_prefix,
                key=f"prefix_{video_name}"
            )
            st.session_state.prefix_settings[video_name] = new_prefix
            st.sidebar.caption(f"→ {new_prefix}_bin_X.mp4 or {new_prefix}_HX.mp4")

        st.sidebar.markdown("---")
        
        st.sidebar.header("3. Process Videos")
        
        if st.sidebar.button("Start Trimming All Videos", type="primary", use_container_width=True):
            os.makedirs(final_output_path, exist_ok=True)
            
            st.subheader("Trimming Process")
            all_output_files = []

            for path in temp_file_paths:
                name = os.path.basename(path)
                config = st.session_state.video_settings[name]

                # Get user-defined prefix for this specific video
                video_prefix = st.session_state.prefix_settings.get(name, name.split('_')[0] if '_' in name else os.path.splitext(name)[0])

                start_time = hms_to_seconds(config["start_h"], config["start_m"], config["start_s"])
                chunk_duration = hms_to_seconds(config["chunk_h"], config["chunk_m"], config["chunk_s"])

                if chunk_duration <= 0:
                    st.warning(f"Skipping {name}: chunk duration must be greater than 0.")
                    continue

                try:
                    duration = float(ffmpeg.probe(path)['format']['duration'])
                except:
                    duration = 86400.0

                if start_time >= duration:
                    st.warning(f"Skipping {name}: start time exceeds duration.")
                    continue

                effective_duration = duration - start_time
                num_chunks = math.ceil(effective_duration / chunk_duration)

                st.write(f"**{name}**: {num_chunks} chunks from {seconds_to_hms(start_time)} (prefix: {video_prefix})")

                video_progress = st.progress(0)
                chunk_status = st.empty()

                for i in range(num_chunks):
                    chunk_start = start_time + i * chunk_duration
                    chunk_end = min(chunk_start + chunk_duration, duration)
                    
                    if chunk_duration == 3600:  
                        hour_label = int(chunk_start // 3600) + 1  
                        output_name = f"{video_prefix}_H{hour_label}.mp4"
                    else:
                        bin_number = i + 1  
                        output_name = f"{video_prefix}_bin_{bin_number}.mp4"
                    
                    output_path = os.path.join(final_output_path, output_name)

                    chunk_status.info(f"Chunk {i+1}/{num_chunks} → {seconds_to_hms(chunk_start)} to {seconds_to_hms(chunk_end)}")

                    (
                        ffmpeg
                        .input(path, ss=chunk_start, t=chunk_duration)
                        .output(output_path, vcodec='libx264', an=None)
                        .overwrite_output()
                        .run()
                    )

                    all_output_files.append(output_path)
                    video_progress.progress((i + 1) / num_chunks)

                chunk_status.success(f"Completed: {name}")
                st.write("---")

            total_size_mb = sum(os.path.getsize(f) for f in all_output_files) / (1024 * 1024)
            if total_size_mb >= ZIP_THRESHOLD_MB:
                zip_name = os.path.basename(os.path.normpath(final_output_path)) + ".zip"
                zip_path = os.path.join(final_output_path, zip_name)
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for f in all_output_files:
                        zipf.write(f, os.path.basename(f))
                st.success(f"Videos zipped at: {zip_path}")
            else:
                st.success(f"Videos saved to: {final_output_path}")

        
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        st.error(f"Unexpected error: {str(e)}")
