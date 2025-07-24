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
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02}:{m:02}:{s:02}"

def crop_trim(temp_file_paths):
    if not temp_file_paths:
        st.error("No files provided")
        return

    ZIP_THRESHOLD_MB = 500

    try:
        for state_key in ['crop_settings', 'frame_images', 'video_durations', 'video_settings', 'prefix_settings']:
            if state_key not in st.session_state:
                st.session_state[state_key] = {}

        st.header("Uploaded Files Info")
        
        st.sidebar.title("Crop & Trim Configuration")
        
        st.sidebar.header("1. Video Selection for Cropping")
        
        selected_idx = st.sidebar.selectbox("Choose a video to crop:", range(len(temp_file_paths)),
                                            format_func=lambda i: os.path.basename(temp_file_paths[i]))
        selected_video_path = temp_file_paths[selected_idx]
        selected_video_name = os.path.basename(selected_video_path)

        st.sidebar.markdown("---")
        
        st.sidebar.header("2. Mouse Setup")
        
        st.sidebar.subheader("Mouse IDs Setup")
        mouse_ids_input = st.sidebar.text_input("Enter mouse IDs (comma-separated)", "1,2,3")
        mouse_ids = [m.strip() for m in mouse_ids_input.split(",") if m.strip().isdigit()]

        if not mouse_ids:
            st.sidebar.warning("Please enter at least one mouse ID.")
            return

        def render_file_info_table():
            file_info_data = []
            for path in temp_file_paths:
                file_name = os.path.basename(path)
                size_mb = os.path.getsize(path) / (1024 * 1024)
                try:
                    if file_name not in st.session_state.video_durations:
                        duration_val = float(ffmpeg.probe(path)['format']['duration'])
                        st.session_state.video_durations[file_name] = duration_val
                    else:
                        duration_val = st.session_state.video_durations[file_name]
                    duration_str = f"{duration_val:.1f}s"
                except:
                    duration_val = 0
                    duration_str = "Unknown"

                crops_dict = st.session_state.crop_settings.get(file_name, {})

                # For the currently selected video, use current mouse_ids
                if file_name == selected_video_name:
                    total_crops = len(mouse_ids)
                    set_mice = []
                    for m in mouse_ids:
                        if crops_dict.get(str(m)) is not None:
                            set_mice.append(f"Mouse {m}")
                    crops_set = len(set_mice)
                else:
                    # For other videos, show previously set crops
                    crops_set = sum(1 for c in crops_dict.values() if c is not None)
                    total_crops = len(crops_dict) if crops_dict else 0
                    set_mice = [f"Mouse {m}" for m in crops_dict.keys() if crops_dict[m] is not None]
                
                if set_mice:
                    crops_detail = f"{crops_set}/{total_crops} ({', '.join(set_mice)})"
                else:
                    crops_detail = f"{crops_set}/{total_crops}"

                # Add trimming info
                trim_config = st.session_state.video_settings.get(file_name, {})
                start_time = hms_to_seconds(trim_config.get("start_h", 0), trim_config.get("start_m", 0), trim_config.get("start_s", 0))
                chunk_time = hms_to_seconds(trim_config.get("chunk_h", 1), trim_config.get("chunk_m", 0), trim_config.get("chunk_s", 0))

                file_info_data.append({
                    "File Name": file_name,
                    "Size (MB)": f"{size_mb:.1f}",
                    "Duration": duration_str,
                    "Crops Set": crops_detail,
                    "Start Time": seconds_to_hms(start_time),
                    "Chunk Duration": seconds_to_hms(chunk_time)
                })

            st.dataframe(file_info_data, use_container_width=True, hide_index=True)

        render_file_info_table()

        # Initialize crop settings properly for the selected video
        if selected_video_name not in st.session_state.crop_settings:
            st.session_state.crop_settings[selected_video_name] = {}

        # Initialize mouse IDs for the selected video
        for mid in mouse_ids:
            if str(mid) not in st.session_state.crop_settings[selected_video_name]:
                st.session_state.crop_settings[selected_video_name][str(mid)] = None

        st.sidebar.markdown("---")
        
        st.sidebar.header("3. Frame Extraction & Cropping")

        selected_mouse_id = st.sidebar.selectbox("Select mouse to crop", mouse_ids,
                                                 format_func=lambda x: f"Mouse {x}")

        try:
            if selected_video_name not in st.session_state.video_durations:
                duration = float(ffmpeg.probe(selected_video_path)['format']['duration'])
                st.session_state.video_durations[selected_video_name] = duration
            else:
                duration = st.session_state.video_durations[selected_video_name]
        except:
            duration = 10.0

        frame_key = f"frame_time_{selected_video_name}"
        if frame_key not in st.session_state:
            st.session_state[frame_key] = duration / 2

        st.sidebar.subheader("Frame Selection")
        frame_time = st.sidebar.slider("Select time (seconds)", 0.0, duration,
                                       value=st.session_state[frame_key], step=0.1,
                                       key=f"slider_{selected_video_name}")

        if st.sidebar.button("Extract Frame", key=f"extract_{selected_video_name}"):
            temp_frame_path = tempfile.mktemp(suffix='.jpg')
            try:
                (
                    ffmpeg.input(selected_video_path, ss=frame_time)
                    .output(temp_frame_path, vframes=1, format='image2', vcodec='mjpeg')
                    .overwrite_output().run(quiet=True)
                )
                frame_image = Image.open(temp_frame_path)
                st.session_state.frame_images[selected_video_name] = frame_image.copy()
                st.session_state[f"frame_extracted_{selected_video_name}"] = True
                frame_image.close()
            except Exception as e:
                st.error(f"Error extracting frame: {str(e)}")
            finally:
                if os.path.exists(temp_frame_path):
                    os.unlink(temp_frame_path)

        if st.session_state.get(f"frame_extracted_{selected_video_name}", False):
            st.subheader(f"Draw Crop Box for Mouse {selected_mouse_id}")
            crop_box = st_cropper(
                st.session_state.frame_images[selected_video_name],
                realtime_update=True, box_color='#0000FF', aspect_ratio=None, return_type='box',
            )

            if st.button("Set Crop for This Mouse"):
                try:
                    if crop_box and all(k in crop_box for k in ['left', 'top', 'width', 'height']):
                        crop_data = {
                            'x': int(round(crop_box['left'])),
                            'y': int(round(crop_box['top'])),
                            'w': int(round(crop_box['width'])),
                            'h': int(round(crop_box['height']))
                        }
                        
                        # Ensure the video exists in crop_settings
                        if selected_video_name not in st.session_state.crop_settings:
                            st.session_state.crop_settings[selected_video_name] = {}
                        
                        # Use string keys for consistency
                        st.session_state.crop_settings[selected_video_name][str(selected_mouse_id)] = crop_data
                        st.success(f"Crop set for Mouse {selected_mouse_id} in {selected_video_name}")
                        st.rerun()
                    else:
                        st.error("Please draw a valid crop box before setting the crop.")
                except Exception as e:
                    st.error(f"Error setting crop: {str(e)}")
                    # Debug information
                    st.write("Debug info:")
                    st.write(f"Selected video: {selected_video_name}")
                    st.write(f"Selected mouse: {selected_mouse_id}")
                    st.write(f"Crop box: {crop_box}")

        st.sidebar.markdown("---")
        
        st.sidebar.header("4. Trimming Settings")
        
        st.sidebar.subheader("Trimming Mode")
        trimming_mode = st.sidebar.radio(
            "How to apply trimming settings:",
            ["Same settings for all videos", "Individual settings per video"],
            index=0
        )
        
        # Video selector for trimming (only if individual mode)
        if trimming_mode == "Individual settings per video":
            st.sidebar.subheader("Video Selection for Trimming")
            trimming_video_idx = st.sidebar.selectbox("Choose video to configure trimming:", 
                                                      range(len(temp_file_paths)),
                                                      format_func=lambda i: os.path.basename(temp_file_paths[i]))
            trimming_video_name = os.path.basename(temp_file_paths[trimming_video_idx])
        else:
            # For same settings mode, use first video as reference
            trimming_video_idx = 0
            trimming_video_name = os.path.basename(temp_file_paths[0])
            st.sidebar.info("Trimming settings will be applied to all videos")
        
        for file_path in temp_file_paths:
            name = os.path.basename(file_path)
            if name not in st.session_state.video_settings:
                duration = st.session_state.video_durations.get(name, 86400.0)
                st.session_state.video_settings[name] = {
                    "duration": duration,
                    "start_h": 0, "start_m": 0, "start_s": 0,
                    "chunk_h": 1, "chunk_m": 0, "chunk_s": 0
                }

        cfg = st.session_state.video_settings[trimming_video_name]
        
        st.sidebar.subheader("Start Time (H:M:S)")
        col1, col2, col3 = st.sidebar.columns(3)
        with col1:
            start_h = st.number_input("H", 0, 23, cfg["start_h"], key=f"{trimming_video_name}_sh", format="%d")
        with col2:
            start_m = st.number_input("M", 0, 59, cfg["start_m"], key=f"{trimming_video_name}_sm", format="%d")
        with col3:
            start_s = st.number_input("S", 0, 59, cfg["start_s"], key=f"{trimming_video_name}_ss", format="%d")

        st.sidebar.subheader("Chunk Duration (H:M:S)")
        col1, col2, col3 = st.sidebar.columns(3)
        with col1:
            chunk_h = st.number_input("H", 0, 24, cfg["chunk_h"], key=f"{trimming_video_name}_ch", format="%d")
        with col2:
            chunk_m = st.number_input("M", 0, 59, cfg["chunk_m"], key=f"{trimming_video_name}_cm", format="%d")
        with col3:
            chunk_s = st.number_input("S", 0, 59, cfg["chunk_s"], key=f"{trimming_video_name}_cs", format="%d")

        # Change button label based on mode
        if trimming_mode == "Same settings for all videos":
            button_label = "Apply Trimming Settings to All Videos"
        else:
            button_label = f"Set Trimming Times for {trimming_video_name}"

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
                    st.sidebar.success("Trimming settings applied to all videos!")
                else:
                    st.sidebar.success(f"Trimming times set for {trimming_video_name}!")

        st.sidebar.markdown("---")
        
        st.sidebar.header("5. Output Configuration")
        
        st.sidebar.subheader("Output Folder")
        OUTPUT_DIR = st.sidebar.text_input("Full output folder path",
                                           os.path.join(os.path.expanduser("~"), "Videos", "CroppedTrimmed"))
        
        folder_exists = os.path.exists(OUTPUT_DIR)
        if folder_exists:
            existing_files = []
            for root, dirs, files in os.walk(OUTPUT_DIR):
                existing_files.extend([f for f in files if f.endswith('.mp4')])
            
            if existing_files:
                st.sidebar.warning(f"Folder exists with {len(existing_files)} video files!")
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
            final_output_dir = f"{OUTPUT_DIR}_{timestamp}"
            st.sidebar.info(f"Will create: {os.path.basename(final_output_dir)}")
        else:
            final_output_dir = OUTPUT_DIR

        st.sidebar.subheader("File Naming")
        
        global_prefix = st.sidebar.text_input("Output file prefix (for all videos):", "processed")
        st.sidebar.caption(f"→ {global_prefix}_mouseX_bin_Y.mp4 or {global_prefix}_mouseX_HY.mp4")

        st.sidebar.markdown("---")
        
        st.sidebar.header("5. Process Videos")

        if st.sidebar.button("Crop and Trim All Videos", use_container_width=True):
            os.makedirs(final_output_dir, exist_ok=True)
            
            st.subheader("Processing Videos...")
            all_output_files = []

            for video_path in temp_file_paths:
                name = os.path.basename(video_path)
                duration = st.session_state.video_durations.get(name, 86400.0)
                crops = st.session_state.crop_settings.get(name, {})
                config = st.session_state.video_settings.get(name, {})
                
                if name == selected_video_name:
                    current_mouse_ids = mouse_ids
                else:
                    crops_dict = st.session_state.crop_settings.get(name, {})
                    current_mouse_ids = [mid for mid in mouse_ids if crops_dict.get(mid) is not None]

                start_time = hms_to_seconds(config["start_h"], config["start_m"], config["start_s"])
                chunk_duration = hms_to_seconds(config["chunk_h"], config["chunk_m"], config["chunk_s"])
                if chunk_duration <= 0 or start_time >= duration:
                    st.warning(f"Skipping {name}: Invalid start time or chunk duration.")
                    continue

                if not current_mouse_ids:
                    st.warning(f"Skipping {name}: No mouse crops defined for current mouse IDs.")
                    continue

                for mouse_id in current_mouse_ids:
                    # Use string keys for consistency
                    crop = crops.get(str(mouse_id))
                    if not crop:
                        st.warning(f"Skipping Mouse {mouse_id} in {name}: No crop data.")
                        continue

                    effective_duration = duration - start_time
                    num_chunks = math.ceil(effective_duration / chunk_duration)
                    st.write(f"**{name} (Mouse {mouse_id})**: {num_chunks} chunks")

                    for i in range(num_chunks):
                        chunk_start = start_time + i * chunk_duration
                        chunk_end = min(chunk_start + chunk_duration, duration)
                        
                        if chunk_duration == 3600: 
                            hour_label = int(chunk_start // 3600) + 1
                            output_file = os.path.join(final_output_dir, f"{global_prefix}_mouse{mouse_id}_H{hour_label}.mp4")
                        else:
                            bin_number = i + 1
                            output_file = os.path.join(final_output_dir, f"{global_prefix}_mouse{mouse_id}_bin_{bin_number}.mp4")

                        try:
                            (
                                ffmpeg.input(video_path, ss=chunk_start, t=chunk_end - chunk_start)
                                .filter('crop', crop['w'], crop['h'], crop['x'], crop['y'])
                                .output(output_file, vcodec='libx264', acodec='aac')
                                .overwrite_output().run(quiet=True)
                            )
                            all_output_files.append(output_file)
                        except Exception as e:
                            st.error(f"Error: {e}")

                    st.write("---")

            total_size_mb = sum(os.path.getsize(f) for f in all_output_files) / (1024 * 1024)
            if total_size_mb >= ZIP_THRESHOLD_MB:
                zip_name = os.path.basename(os.path.normpath(final_output_dir)) + ".zip"
                zip_path = os.path.join(final_output_dir, zip_name)
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for f in all_output_files:
                        zipf.write(f, os.path.basename(f))
                st.success(f"Videos zipped at: {zip_path}")
            else:
                st.success(f"Videos saved to: {final_output_dir}")


    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
