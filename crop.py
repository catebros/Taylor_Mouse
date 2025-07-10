import streamlit as st
import os
import ffmpeg
from streamlit_cropper import st_cropper
from PIL import Image
import tempfile


def crop(temp_file_paths):
    if not temp_file_paths:
        st.error("No files provided")
        return

    try:
        if 'crop_settings' not in st.session_state:
            st.session_state.crop_settings = {}

        if 'frame_images' not in st.session_state:
            st.session_state.frame_images = {}

        if 'video_durations' not in st.session_state:
            st.session_state.video_durations = {}

        if 'refresh_counter' not in st.session_state:
            st.session_state.refresh_counter = 0

        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")

        # Build and display the file table first
        st.header(f"Uploaded Files ({len(temp_file_paths)})")
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

            crop_status = "Yes" if file_name in st.session_state.crop_settings else "No"

            file_info_data.append({
                "File Name": file_name,
                "Size (MB)": f"{size_mb:.1f}",
                "Duration": duration_str,
                "Crop Set": crop_status
            })

        st.dataframe(file_info_data, use_container_width=True, hide_index=True)

        selected_idx = st.sidebar.selectbox(
            "Choose a video:",
            range(len(temp_file_paths)),
            format_func=lambda i: os.path.basename(temp_file_paths[i])
        )

        selected_video_path = temp_file_paths[selected_idx]
        selected_video_name = os.path.basename(selected_video_path)

        # Sidebar input
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

        if st.session_state.get(f"frame_extracted_{selected_video_name}", False) and not st.session_state.get("processing_started", False):
            st.subheader("Draw Crop Box")
            crop_box = st_cropper(
                st.session_state.frame_images[selected_video_name],
                realtime_update=True,
                box_color='#0000FF',
                aspect_ratio=None,
                return_type='box',
            )

            if st.button("Set Crop for This Video"):
                if crop_box and all(k in crop_box for k in ['left', 'top', 'width', 'height']):
                    st.session_state.crop_settings[selected_video_name] = {
                        'x': int(round(crop_box['left'])),
                        'y': int(round(crop_box['top'])),
                        'w': int(round(crop_box['width'])),
                        'h': int(round(crop_box['height']))
                    }
                    st.success(f"Crop set for {selected_video_name}")
                    st.rerun()
                else:
                    st.warning("Please draw a crop box before saving.")

        # Output settings
        st.sidebar.subheader("Output Settings")
        OUTPUT_DIR = st.sidebar.text_input("Folder name in Downloads", "Cropped_Videos")
        full_output_path = os.path.join(os.path.expanduser("~"), "Downloads", OUTPUT_DIR)
        os.makedirs(full_output_path, exist_ok=True)

        if st.sidebar.button("Crop All Videos"):
            st.session_state["processing_started"] = True

            if not st.session_state.crop_settings:
                st.sidebar.warning("No crops have been set.")
            else:
                st.subheader("Cropping Process")

                for video_idx, video_path in enumerate(temp_file_paths):
                    video_name = os.path.basename(video_path)
                    crop_data = st.session_state.crop_settings.get(video_name)

                    if not crop_data:
                        st.warning(f"Skipping {video_name}: no crop defined.")
                        continue

                    output_file = os.path.join(full_output_path, f'{os.path.splitext(video_name)[0]}_cropped.mp4')

                    st.write(f"**Video {video_idx + 1}/{len(temp_file_paths)}: {video_name}**")
                    st.write(f"Cropping to {crop_data['w']}x{crop_data['h']} at position ({crop_data['x']}, {crop_data['y']})")

                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    status_text.info(f"Processing {video_name}...")

                    try:
                        (
                            ffmpeg
                            .input(video_path)
                            .filter('crop', crop_data['w'], crop_data['h'], crop_data['x'], crop_data['y'])
                            .output(output_file, vcodec='libx264', acodec='aac')
                            .overwrite_output()
                            .run(quiet=True)
                        )

                        progress_bar.progress(1.0)
                        status_text.success(f"Completed {video_name}")

                    except Exception as e:
                        status_text.error(f"Error cropping {video_name}: {str(e)}")

                    st.write("---")

                st.success(f"All finished! Cropped videos saved to: {full_output_path}")

    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")