import streamlit as st
import os
import ffmpeg
import math
import zipfile


def hms_to_seconds(h, m, s):
    return h * 3600 + m * 60 + s


def seconds_to_hms(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) % 60)
    s = int(seconds % 60)
    return f"{h:02}:{m:02}:{s:02}"


def trim(temp_file_paths):
    if not temp_file_paths:
        st.error("No files provided")
        return

    try:
        ZIP_THRESHOLD_MB = 500 
        st.sidebar.header("Video Selection")

        video_names = [os.path.basename(p) for p in temp_file_paths]
        selected_idx = st.sidebar.selectbox("Select video to configure:", range(len(video_names)), format_func=lambda i: video_names[i])
        selected_path = temp_file_paths[selected_idx]
        selected_name = video_names[selected_idx]

        if "video_settings" not in st.session_state:
            st.session_state.video_settings = {}

        if selected_name not in st.session_state.video_settings:
            try:
                duration = float(ffmpeg.probe(selected_path)['format']['duration'])
            except:
                duration = 86400.0
            st.session_state.video_settings[selected_name] = {
                "duration": duration,
                "start_h": 0,
                "start_m": 0,
                "start_s": 0,
                "chunk_h": 1,
                "chunk_m": 0,
                "chunk_s": 0,
            }

        cfg = st.session_state.video_settings[selected_name]

        st.sidebar.markdown("### Start Time (H:M:S)")
        cfg["start_h"] = st.sidebar.number_input("Start Hour", 0, 24, cfg["start_h"], key=f"{selected_name}_sh")
        cfg["start_m"] = st.sidebar.number_input("Start Minute", 0, 59, cfg["start_m"], key=f"{selected_name}_sm")
        cfg["start_s"] = st.sidebar.number_input("Start Second", 0, 59, cfg["start_s"], key=f"{selected_name}_ss")

        st.sidebar.markdown("### Chunk Duration (H:M:S)")
        cfg["chunk_h"] = st.sidebar.number_input("Chunk Hour", 0, 24, cfg["chunk_h"], key=f"{selected_name}_ch")
        cfg["chunk_m"] = st.sidebar.number_input("Chunk Minute", 0, 59, cfg["chunk_m"], key=f"{selected_name}_cm")
        cfg["chunk_s"] = st.sidebar.number_input("Chunk Second", 0, 59, cfg["chunk_s"], key=f"{selected_name}_cs")

        st.sidebar.header("Output Folder")
        output_base_path = st.sidebar.text_input("Full output folder path", os.path.join(os.path.expanduser("~"), "Videos", "Trimmed"))
        os.makedirs(output_base_path, exist_ok=True)

        # Show summary table
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

        if st.sidebar.button("Start Trimming All Videos", type="primary"):
            st.subheader("Trimming Process")
            all_output_files = []

            for path in temp_file_paths:
                name = os.path.basename(path)
                config = st.session_state.video_settings[name]

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
                base_filename = os.path.splitext(name)[0]
                output_dir = os.path.join(output_base_path, base_filename)
                os.makedirs(output_dir, exist_ok=True)

                st.write(f"**{name}**: {num_chunks} chunks from {seconds_to_hms(start_time)}")

                video_progress = st.progress(0)
                chunk_status = st.empty()

                for i in range(num_chunks):
                    chunk_start = start_time + i * chunk_duration
                    chunk_end = min(chunk_start + chunk_duration, duration)
                    hour_label = int(chunk_start // 3600)
                    output_name = f"{base_filename}_H{hour_label}.mp4"
                    output_path = os.path.join(output_dir, output_name)

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
                zip_name = os.path.basename(os.path.normpath(output_base_path)) + ".zip"
                zip_path = os.path.join(output_base_path, zip_name)
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for f in all_output_files:
                        zipf.write(f, os.path.relpath(f, output_base_path))
                st.success(f"Videos zipped at: {zip_path}")
            else:
                st.success(f"Videos saved to: {output_base_path}")

        
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
