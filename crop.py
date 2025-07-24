import streamlit as st
import os
import ffmpeg
import zipfile
from streamlit_cropper import st_cropper
from PIL import Image
import tempfile


def crop(temp_file_paths):
    if not temp_file_paths:
        st.error("No files provided")
        return

    ZIP_THRESHOLD_MB = 500  # Zip

    try:
        if 'crop_settings' not in st.session_state:
            st.session_state.crop_settings = {}

        if 'frame_images' not in st.session_state:
            st.session_state.frame_images = {}

        if 'video_durations' not in st.session_state:
            st.session_state.video_durations = {}

        st.header(f"Uploaded Files ({len(temp_file_paths)})")
        
        st.sidebar.title("Crop Configuration")
        
        st.sidebar.header("1. Video & Mouse Setup")
        
        st.sidebar.subheader("Video Selection")
        selected_idx = st.sidebar.selectbox(
            "Choose a video:",
            range(len(temp_file_paths)),
            format_func=lambda i: os.path.basename(temp_file_paths[i])
        )

        selected_video_path = temp_file_paths[selected_idx]
        selected_video_name = os.path.basename(selected_video_path)

        st.sidebar.subheader("Mouse IDs Setup")
        mouse_ids_input = st.sidebar.text_input("Enter mouse IDs in the video (comma-separated)", "1,2,3")
        mouse_ids = [m.strip() for m in mouse_ids_input.split(",") if m.strip().isdigit()]

        if not mouse_ids:
            st.sidebar.warning("Please enter at least one mouse ID.")
            return

        # Initialize crop settings properly for the selected video
        if selected_video_name not in st.session_state.crop_settings:
            st.session_state.crop_settings[selected_video_name] = {}

        # Initialize mouse IDs for the selected video
        for mid in mouse_ids:
            if str(mid) not in st.session_state.crop_settings[selected_video_name]:
                st.session_state.crop_settings[selected_video_name][str(mid)] = None

        def render_file_info_table():
            file_info_data = []
            for path in temp_file_paths:
                file_name = os.path.basename(path)
                try:
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                except:
                    size_mb = 0

                try:
                    if file_name not in st.session_state.video_durations:
                        duration_val = float(ffmpeg.probe(path)['format']['duration'])
                        st.session_state.video_durations[file_name] = duration_val
                    else:
                        duration_val = st.session_state.video_durations[file_name]
                    duration_str = f"{duration_val:.1f}s"
                except:
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

                file_info_data.append({
                    "File Name": file_name,
                    "Size (MB)": f"{size_mb:.1f}",
                    "Duration": duration_str,
                    "Crops Set": crops_detail
                })

            st.dataframe(file_info_data, use_container_width=True, hide_index=True)

        # Render table only once, after initialization
        render_file_info_table()

        selected_mouse_id = st.sidebar.selectbox("Select mouse to crop", mouse_ids, format_func=lambda x: f"Mouse {x}")

        st.sidebar.markdown("---")
        
        st.sidebar.header("2. Frame Extraction & Cropping")

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
        frame_time = st.sidebar.slider(
            "Select time (seconds)",
            min_value=0.0,
            max_value=duration,
            value=st.session_state[frame_key],
            step=0.1,
            key=f"slider_{selected_video_name}"
        )

        if st.sidebar.button("Extract Frame", key=f"extract_{selected_video_name}"):
            temp_frame_path = tempfile.mktemp(suffix='.jpg')
            try:
                (
                    ffmpeg
                    .input(selected_video_path, ss=frame_time)
                    .output(temp_frame_path, vframes=1, format='image2', vcodec='mjpeg')
                    .overwrite_output()
                    .run(quiet=True)
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
                realtime_update=True,
                box_color='#0000FF',
                aspect_ratio=None,
                return_type='box',
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

        st.sidebar.markdown("---")
        
        st.sidebar.header("3. Output Configuration")
        
        st.sidebar.subheader("Output Folder")
        OUTPUT_DIR = st.sidebar.text_input("Full output folder path", os.path.join(os.path.expanduser("~"), "Videos", "Cropped"))
        
        folder_exists = os.path.exists(OUTPUT_DIR)
        if folder_exists:
            existing_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.mp4')]
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
            st.sidebar.caption(f"→ {new_prefix}_mouseX.mp4")

        st.sidebar.markdown("---")
        
        st.sidebar.header("4. Process Videos")

        if st.sidebar.button("Crop All Videos", use_container_width=True):
            os.makedirs(final_output_dir, exist_ok=True)
            
            st.session_state[f"frame_extracted_{selected_video_name}"] = False
            st.session_state["processing_started"] = True

            if not st.session_state.crop_settings:
                st.sidebar.warning("No crops have been set.")
            else:
                st.subheader("Cropping Process")
                output_files = []

                for video_idx, video_path in enumerate(temp_file_paths):
                    video_name = os.path.basename(video_path)
                    
                    video_prefix = st.session_state.prefix_settings.get(video_name, video_name.split('_')[0] if '_' in video_name else os.path.splitext(video_name)[0])
                    
                    if video_name == selected_video_name:
                        current_mouse_ids = mouse_ids  
                    else:
                        crops_dict = st.session_state.crop_settings.get(video_name, {})
                        current_mouse_ids = [mid for mid in mouse_ids if crops_dict.get(mid) is not None]
                    
                    if not current_mouse_ids:
                        st.warning(f"Skipping {video_name}: No mouse crops defined for current mouse IDs.")
                        continue

                    for mouse_id in current_mouse_ids:
                        # Use string keys for consistency
                        crop_data = st.session_state.crop_settings.get(video_name, {}).get(str(mouse_id))
                        
                        if not crop_data:
                            st.warning(f"Skipping {video_name} Mouse {mouse_id}: no crop defined.")
                            continue

                        output_file = os.path.join(final_output_dir, f'{video_prefix}_mouse{mouse_id}.mp4')

                        st.write(f"**{video_name} (Mouse {mouse_id})** → {video_prefix}_mouse{mouse_id}.mp4")
                        st.write(f"Cropping to {crop_data['w']}x{crop_data['h']} at ({crop_data['x']}, {crop_data['y']})")

                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        status_text.info(f"Processing {video_name} Mouse {mouse_id}...")

                        try:
                            (
                                ffmpeg
                                .input(video_path)
                                .filter('crop', crop_data['w'], crop_data['h'], crop_data['x'], crop_data['y'])
                                .output(output_file, vcodec='libx264', acodec='aac', an=None)
                                .overwrite_output()
                                .run(quiet=True)
                            )

                            output_files.append(output_file)
                            progress_bar.progress(1.0)
                            status_text.success(f"Completed {video_name} Mouse {mouse_id}")

                        except Exception as e:
                            status_text.error(f"Error cropping {video_name} Mouse {mouse_id}: {str(e)}")

                        st.write("---")

                total_size_mb = sum(os.path.getsize(f) for f in output_files) / (1024 * 1024)
                if total_size_mb >= ZIP_THRESHOLD_MB:
                    zip_name = os.path.basename(os.path.normpath(OUTPUT_DIR)) + ".zip"
                    zip_path = os.path.join(OUTPUT_DIR, zip_name)                  
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for f in output_files:
                            zipf.write(f, os.path.basename(f))
                    st.success(f"Files zipped to: {zip_path}")
                else:
                    st.success(f"All videos saved to: {OUTPUT_DIR}")


    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
