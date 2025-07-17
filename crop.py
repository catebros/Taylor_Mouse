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

        def render_file_info_table():
            file_info_data = []
            for path in temp_file_paths:
                file_name = os.path.basename(path)
                try:
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                except:
                    size_mb = 0

                try:
                    duration_val = st.session_state.video_durations.get(file_name, float(ffmpeg.probe(path)['format']['duration']))
                    duration_str = f"{duration_val:.1f}s"
                except:
                    duration_str = "Unknown"

                crops_dict = st.session_state.crop_settings.get(file_name, {})
                crops_set = sum(1 for c in crops_dict.values() if c is not None)
                total_crops = len(crops_dict)
                set_mice = [f"Mouse {m}" for m in crops_dict if crops_dict[m] is not None]
                crops_detail = f"{crops_set}/{total_crops}" + (f" ({', '.join(set_mice)})" if set_mice else "")

                file_info_data.append({
                    "File Name": file_name,
                    "Size (MB)": f"{size_mb:.1f}",
                    "Duration": duration_str,
                    "Crops Set": crops_detail
                })

            st.dataframe(file_info_data, use_container_width=True, hide_index=True)

        if 'refresh_counter' not in st.session_state:
            st.session_state.refresh_counter = 0

        if st.button("Refresh Table"):
            st.session_state.refresh_counter += 1

        render_file_info_table()



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

        if selected_video_name not in st.session_state.crop_settings:
            st.session_state.crop_settings[selected_video_name] = {}

        for mid in mouse_ids:
            if mid not in st.session_state.crop_settings[selected_video_name]:
                st.session_state.crop_settings[selected_video_name][mid] = None

        selected_mouse_id = st.sidebar.selectbox("Select mouse to crop", mouse_ids, format_func=lambda x: f"Mouse {x}")

        st.sidebar.subheader("Extract Frame for Cropping")

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
                if crop_box and all(k in crop_box for k in ['left', 'top', 'width', 'height']):
                    crop_data = {
                        'x': int(round(crop_box['left'])),
                        'y': int(round(crop_box['top'])),
                        'w': int(round(crop_box['width'])),
                        'h': int(round(crop_box['height']))
                    }
                    st.session_state.crop_settings[selected_video_name][selected_mouse_id] = crop_data
                    st.success(f"Crop set for Mouse {selected_mouse_id} in {selected_video_name}")

        # Output settings
        st.sidebar.subheader("Output Settings")
        OUTPUT_DIR = st.sidebar.text_input("Full output folder path", os.path.join(os.path.expanduser("~"), "Videos", "Cropped"))
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        if st.sidebar.button("Crop All Videos"):
            st.session_state[f"frame_extracted_{selected_video_name}"] = False
            st.session_state["processing_started"] = True

            if not st.session_state.crop_settings:
                st.sidebar.warning("No crops have been set.")
            else:
                st.subheader("Cropping Process")
                output_files = []

                for video_idx, video_path in enumerate(temp_file_paths):
                    video_name = os.path.basename(video_path)
                    crops = st.session_state.crop_settings.get(video_name, {})

                    for mouse_id, crop_data in crops.items():
                        if not crop_data:
                            st.warning(f"Skipping {video_name} Mouse {mouse_id}: no crop defined.")
                            continue

                        output_file = os.path.join(OUTPUT_DIR, f'{os.path.splitext(video_name)[0]}_mouse{mouse_id}.mp4')

                        st.write(f"**{video_name} (Mouse {mouse_id})**")
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
