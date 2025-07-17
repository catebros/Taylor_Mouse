# crop_trim.py
import streamlit as st
import os
import ffmpeg
import zipfile
import tempfile
import math
from streamlit_cropper import st_cropper
from PIL import Image


def hms_to_seconds(h, m, s):
    return h * 3600 + m * 60 + s


def seconds_to_hms(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) % 60)
    s = int(seconds % 60)
    return f"{h:02}:{m:02}:{s:02}"


def crop_trim(temp_file_paths):
    if not temp_file_paths:
        st.error("No files provided")
        return

    ZIP_THRESHOLD_MB = 500

    # Init session state
    for state_key in ['crop_settings', 'frame_images', 'video_durations', 'video_settings']:
        if state_key not in st.session_state:
            st.session_state[state_key] = {}

    st.header("Uploaded Files Info")
    file_info_data = []
    for path in temp_file_paths:
        file_name = os.path.basename(path)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        try:
            duration_val = float(ffmpeg.probe(path)['format']['duration'])
        except:
            duration_val = 0
        st.session_state.video_durations[file_name] = duration_val
        duration_str = f"{duration_val:.1f}s"

        crops_dict = st.session_state.crop_settings.get(file_name, {})
        crops_set = sum(1 for c in crops_dict.values() if c is not None)
        set_mice = [f"Mouse {m}" for m in crops_dict if crops_dict[m] is not None]
        crops_detail = f"{crops_set}/{len(crops_dict)}" + (f" ({', '.join(set_mice)})" if set_mice else "")

        file_info_data.append({
            "File Name": file_name,
            "Size (MB)": f"{size_mb:.1f}",
            "Duration": duration_str,
            "Crops Set": crops_detail
        })

    st.dataframe(file_info_data, use_container_width=True, hide_index=True)

    # Select video and mouse
    selected_idx = st.sidebar.selectbox("Choose a video:", range(len(temp_file_paths)),
                                        format_func=lambda i: os.path.basename(temp_file_paths[i]))
    selected_video_path = temp_file_paths[selected_idx]
    selected_video_name = os.path.basename(selected_video_path)

    st.sidebar.subheader("Mouse IDs Setup")
    mouse_ids_input = st.sidebar.text_input("Enter mouse IDs (comma-separated)", "1,2,3")
    mouse_ids = [m.strip() for m in mouse_ids_input.split(",") if m.strip().isdigit()]

    if not mouse_ids:
        st.sidebar.warning("Please enter at least one mouse ID.")
        return

    if selected_video_name not in st.session_state.crop_settings:
        st.session_state.crop_settings[selected_video_name] = {}

    for mid in mouse_ids:
        if mid not in st.session_state.crop_settings[selected_video_name]:
            st.session_state.crop_settings[selected_video_name][mid] = None

    selected_mouse_id = st.sidebar.selectbox("Select mouse to crop", mouse_ids,
                                             format_func=lambda x: f"Mouse {x}")

    # Extract frame
    duration = st.session_state.video_durations.get(selected_video_name, 10.0)
    frame_key = f"frame_time_{selected_video_name}"
    if frame_key not in st.session_state:
        st.session_state[frame_key] = duration / 2

    frame_time = st.sidebar.slider("Select time (seconds)", 0.0, duration,
                                   value=st.session_state[frame_key], step=0.1,
                                   key=f"slider_{selected_video_name}")

    if st.sidebar.button("Extract Frame"):
        temp_frame_path = tempfile.mktemp(suffix='.jpg')
        try:
            (
                ffmpeg.input(selected_video_path, ss=frame_time)
                .output(temp_frame_path, vframes=1, format='image2', vcodec='mjpeg')
                .overwrite_output().run(quiet=True)
            )
            frame_image = Image.open(temp_frame_path)
            st.session_state.frame_images[selected_video_name] = frame_image.copy()
            frame_image.close()
        except Exception as e:
            st.error(f"Error extracting frame: {str(e)}")
        finally:
            if os.path.exists(temp_frame_path):
                os.unlink(temp_frame_path)

    if selected_video_name in st.session_state.frame_images:
        st.subheader(f"Draw Crop Box for Mouse {selected_mouse_id}")
        crop_box = st_cropper(
            st.session_state.frame_images[selected_video_name],
            realtime_update=True, box_color='#0000FF', aspect_ratio=None, return_type='box',
        )

        if st.button("Set Crop for This Mouse"):
            if crop_box and all(k in crop_box for k in ['left', 'top', 'width', 'height']):
                crop_data = {
                    'x': int(round(crop_box['left'])),
                    'y': int(round(crop_box['top'])),
                    'w': int(round(crop_box['width'])),
                    'h': int(round(crop_box['height']))
                }
                st.session_state.crop_settings[selected_video_name][selected_mouse_id] = crop_data
                st.success(f"Crop set for Mouse {selected_mouse_id} in {selected_video_name}")

    # Trimming + Cropping Parameters
    st.sidebar.header("Trimming Settings")
    for file_path in temp_file_paths:
        name = os.path.basename(file_path)
        if name not in st.session_state.video_settings:
            duration = st.session_state.video_durations.get(name, 86400.0)
            st.session_state.video_settings[name] = {
                "duration": duration,
                "start_h": 0, "start_m": 0, "start_s": 0,
                "chunk_h": 1, "chunk_m": 0, "chunk_s": 0
            }

    cfg = st.session_state.video_settings[selected_video_name]
    st.sidebar.markdown("### Start Time")
    cfg["start_h"] = st.sidebar.number_input("Hour", 0, 24, cfg["start_h"])
    cfg["start_m"] = st.sidebar.number_input("Minute", 0, 59, cfg["start_m"])
    cfg["start_s"] = st.sidebar.number_input("Second", 0, 59, cfg["start_s"])

    st.sidebar.markdown("### Chunk Duration")
    cfg["chunk_h"] = st.sidebar.number_input("Chunk Hour", 0, 24, cfg["chunk_h"])
    cfg["chunk_m"] = st.sidebar.number_input("Chunk Minute", 0, 59, cfg["chunk_m"])
    cfg["chunk_s"] = st.sidebar.number_input("Chunk Second", 0, 59, cfg["chunk_s"])

    st.sidebar.subheader("Output Folder")
    OUTPUT_DIR = st.sidebar.text_input("Full output folder path",
                                       os.path.join(os.path.expanduser("~"), "Videos", "CroppedTrimmed"))
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if st.sidebar.button("Crop and Trim All Videos"):
        st.subheader("Processing Videos...")
        all_output_files = []

        for video_path in temp_file_paths:
            name = os.path.basename(video_path)
            duration = st.session_state.video_durations.get(name, 86400.0)
            crops = st.session_state.crop_settings.get(name, {})
            config = st.session_state.video_settings.get(name, {})

            start_time = hms_to_seconds(config["start_h"], config["start_m"], config["start_s"])
            chunk_duration = hms_to_seconds(config["chunk_h"], config["chunk_m"], config["chunk_s"])
            if chunk_duration <= 0 or start_time >= duration:
                st.warning(f"Skipping {name}: Invalid start time or chunk duration.")
                continue

            for mouse_id, crop in crops.items():
                if not crop:
                    st.warning(f"Skipping Mouse {mouse_id} in {name}: No crop data.")
                    continue

                output_base = os.path.join(OUTPUT_DIR, f"{os.path.splitext(name)[0]}_mouse{mouse_id}")
                os.makedirs(output_base, exist_ok=True)

                effective_duration = duration - start_time
                num_chunks = math.ceil(effective_duration / chunk_duration)
                st.write(f"**{name} (Mouse {mouse_id})**: {num_chunks} chunks")

                for i in range(num_chunks):
                    chunk_start = start_time + i * chunk_duration
                    chunk_end = min(chunk_start + chunk_duration, duration)
                    hour_label = int(chunk_start // 3600)
                    output_file = os.path.join(output_base, f"{os.path.splitext(name)[0]}_mouse{mouse_id}_H{hour_label}_chunk{i+1}.mp4")

                    try:
                        (
                            ffmpeg.input(video_path, ss=chunk_start, t=chunk_end - chunk_start)
                            .filter('crop', crop['w'], crop['h'], crop['x'], crop['y'])
                            .output(output_file, vcodec='libx264', acodec='aac', an=None)
                            .overwrite_output().run(quiet=True)
                        )
                        all_output_files.append(output_file)
                    except Exception as e:
                        st.error(f"Error: {e}")

                st.write("---")

        total_size_mb = sum(os.path.getsize(f) for f in all_output_files) / (1024 * 1024)
        if total_size_mb >= ZIP_THRESHOLD_MB:
            zip_name = "output_videos.zip"
            zip_path = os.path.join(OUTPUT_DIR, zip_name)
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for f in all_output_files:
                    zipf.write(f, os.path.relpath(f, OUTPUT_DIR))
            st.success(f"Videos zipped at: {zip_path}")
        else:
            st.success(f"Videos saved to: {OUTPUT_DIR}")
