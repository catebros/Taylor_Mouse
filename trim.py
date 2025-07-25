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
            start_h = st.number_input("H", 0, 23, cfg["start_h"], key=f"trim_start_h_{selected_idx}_{selected_name}", format="%d")
        with col2:
            start_m = st.number_input("M", 0, 59, cfg["start_m"], key=f"trim_start_m_{selected_idx}_{selected_name}", format="%d")
        with col3:
            start_s = st.number_input("S", 0, 59, cfg["start_s"], key=f"trim_start_s_{selected_idx}_{selected_name}", format="%d")

        st.sidebar.subheader("Chunk Duration (H:M:S)")
        col1, col2, col3 = st.sidebar.columns(3)
        with col1:
            chunk_h = st.number_input("H", 0, 24, cfg["chunk_h"], key=f"trim_chunk_h_{selected_idx}_{selected_name}", format="%d")
        with col2:
            chunk_m = st.number_input("M", 0, 59, cfg["chunk_m"], key=f"trim_chunk_m_{selected_idx}_{selected_name}", format="%d")
        with col3:
            chunk_s = st.number_input("S", 0, 59, cfg["chunk_s"], key=f"trim_chunk_s_{selected_idx}_{selected_name}", format="%d")

        if trimming_mode == "Same settings for all videos":
            button_label = "Apply Settings to All Videos"
        else:
            button_label = f"Set Times for {selected_name}"

        if st.sidebar.button(button_label, type="secondary"):
            start_total = hms_to_seconds(start_h, start_m, start_s)
            chunk_total = hms_to_seconds(chunk_h, chunk_m, chunk_s)
            available_time = cfg["duration"] - start_total
            
            if chunk_total <= 0:
                st.sidebar.error("Bin duration must be greater than 0!")
            elif start_total >= cfg["duration"]:
                st.sidebar.error("Start time exceeds video duration!")
            elif chunk_total > available_time:
                st.sidebar.error(f"Bin duration ({seconds_to_hms(chunk_total)}) exceeds available time ({seconds_to_hms(available_time)})!")
            else:
                cfg["start_h"] = start_h
                cfg["start_m"] = start_m
                cfg["start_s"] = start_s
                cfg["chunk_h"] = chunk_h
                cfg["chunk_m"] = chunk_m
                cfg["chunk_s"] = chunk_s
                
                if trimming_mode == "Same settings for all videos":
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
                
                st.rerun()

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
                "Bin Duration": seconds_to_hms(chunk)
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
        
        all_prefixes = []
        duplicate_found = False
        
        for path in temp_file_paths:
            video_name = os.path.basename(path)
            current_prefix = st.session_state.prefix_settings[video_name]
            
            new_prefix = st.sidebar.text_input(
                f"Prefix for {video_name}:",
                value=current_prefix,
                key=f"prefix_{video_name}"
            )
            
            if new_prefix != current_prefix:
                st.session_state.prefix_settings[video_name] = new_prefix
            
            st.sidebar.caption(f"{new_prefix}_bin_X.mp4 or {new_prefix}_HX.mp4")
            
            all_prefixes.append(new_prefix)
        
        if len(all_prefixes) != len(set(all_prefixes)):
            duplicate_found = True
            st.sidebar.error("Duplicate prefixes detected! Files will overwrite each other.")
            
            from collections import Counter
            prefix_counts = Counter(all_prefixes)
            duplicates = [prefix for prefix, count in prefix_counts.items() if count > 1]
            st.sidebar.error(f"Duplicated prefixes: {', '.join(duplicates)}")
            
            st.sidebar.subheader("Solutions:")
            naming_strategy = st.sidebar.radio(
                "Choose how to handle duplicate names:",
                [
                    "Fix prefixes manually (recommended)",
                    "Use continuous bin numbering across all videos"
                ]
            )
        else:
            naming_strategy = "Fix prefixes manually (recommended)"

        st.sidebar.markdown("---")
        
        st.sidebar.header("3. Process Videos")
        
        if duplicate_found and naming_strategy == "Fix prefixes manually (recommended)":
            st.sidebar.error("Please fix duplicate prefixes before processing")
            process_button_disabled = True
        else:
            process_button_disabled = False
        
        if st.sidebar.button("Start Trimming All Videos", type="primary", use_container_width=True, disabled=process_button_disabled):
            os.makedirs(final_output_path, exist_ok=True)
            
            st.subheader("Trimming Process")
            all_output_files = []
            
            if naming_strategy == "Use continuous bin numbering across all videos":
                global_bin_counter = 1
                
                for path in temp_file_paths:
                    name = os.path.basename(path)
                    config = st.session_state.video_settings[name]

                    video_prefix = st.session_state.prefix_settings.get(name, name.split('_')[0] if '_' in name else os.path.splitext(name)[0])

                    start_time = hms_to_seconds(config["start_h"], config["start_m"], config["start_s"])
                    bin_duration = hms_to_seconds(config["chunk_h"], config["chunk_m"], config["chunk_s"])

                    if bin_duration <= 0:
                        st.warning(f"Skipping {name}: bin duration must be greater than 0.")
                        continue

                    try:
                        duration = float(ffmpeg.probe(path)['format']['duration'])
                    except:
                        duration = 86400.0

                    if start_time >= duration:
                        st.warning(f"Skipping {name}: start time exceeds duration.")
                        continue

                    effective_duration = duration - start_time
                    num_bins = math.ceil(effective_duration / bin_duration)

                    st.write(f"**{name}**: {num_bins} bins from {seconds_to_hms(start_time)} (prefix: {video_prefix}) [Bins {global_bin_counter}-{global_bin_counter + num_bins - 1}]")

                    video_progress = st.progress(0)
                    bin_status = st.empty()

                    for i in range(num_bins):
                        bin_start = start_time + i * bin_duration
                        bin_end = min(bin_start + bin_duration, duration)
                        
                        if bin_duration == 3600:  
                            hour_label = int(bin_start // 3600) + 1  
                            output_name = f"{video_prefix}_H{hour_label}.mp4"
                        else:
                            output_name = f"{video_prefix}_bin_{global_bin_counter}.mp4"
                        
                        output_path = os.path.join(final_output_path, output_name)

                        bin_status.info(f"Bin {global_bin_counter} → {seconds_to_hms(bin_start)} to {seconds_to_hms(bin_end)}")

                        (
                            ffmpeg
                            .input(path, ss=bin_start, t=bin_duration)
                            .output(output_path, vcodec='libx264', an=None)
                            .overwrite_output()
                            .run()
                        )

                        all_output_files.append(output_path)
                        video_progress.progress((i + 1) / num_bins)
                        global_bin_counter += 1

                    bin_status.success(f"Completed: {name}")
                    st.write("---")
            else:
                used_filenames = set()

                for path in temp_file_paths:
                    name = os.path.basename(path)
                    config = st.session_state.video_settings[name]

                    video_prefix = st.session_state.prefix_settings.get(name, name.split('_')[0] if '_' in name else os.path.splitext(name)[0])

                    start_time = hms_to_seconds(config["start_h"], config["start_m"], config["start_s"])
                    bin_duration = hms_to_seconds(config["chunk_h"], config["chunk_m"], config["chunk_s"])

                    if bin_duration <= 0:
                        st.warning(f"Skipping {name}: bin duration must be greater than 0.")
                        continue

                    try:
                        duration = float(ffmpeg.probe(path)['format']['duration'])
                    except:
                        duration = 86400.0

                    if start_time >= duration:
                        st.warning(f"Skipping {name}: start time exceeds duration.")
                        continue

                    effective_duration = duration - start_time
                    num_bins = math.ceil(effective_duration / bin_duration)

                    st.write(f"**{name}**: {num_bins} bins from {seconds_to_hms(start_time)} (prefix: {video_prefix})")

                    video_progress = st.progress(0)
                    bin_status = st.empty()

                    for i in range(num_bins):
                        bin_start = start_time + i * bin_duration
                        bin_end = min(bin_start + bin_duration, duration)
                        
                        if bin_duration == 3600:  
                            hour_label = int(bin_start // 3600) + 1  
                            base_output_name = f"{video_prefix}_H{hour_label}.mp4"
                        else:
                            bin_number = i + 1  
                            base_output_name = f"{video_prefix}_bin_{bin_number}.mp4"
                        
                        output_name = base_output_name
                        counter = 1
                        while output_name in used_filenames:
                            name_without_ext = os.path.splitext(base_output_name)[0]
                            output_name = f"{name_without_ext}_{counter}.mp4"
                            counter += 1
                        
                        used_filenames.add(output_name)
                        output_path = os.path.join(final_output_path, output_name)

                        bin_status.info(f"Bin {i+1}/{num_bins} → {seconds_to_hms(bin_start)} to {seconds_to_hms(bin_end)}")

                        (
                            ffmpeg
                            .input(path, ss=bin_start, t=bin_duration)
                            .output(output_path, vcodec='libx264', an=None)
                            .overwrite_output()
                            .run()
                        )

                        all_output_files.append(output_path)
                        video_progress.progress((i + 1) / num_bins)

                    bin_status.success(f"Completed: {name}")
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
