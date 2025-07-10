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

        if 'num_crops' not in st.session_state:
            st.session_state.num_crops = {}

        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")

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

            crops = st.session_state.crop_settings.get(file_name, [])
            crops_set = len([c for c in crops if c is not None])
            total_crops = st.session_state.num_crops.get(file_name, 1)
            
            # Show which specific crops are set
            set_crops = [str(i + 1) for i, c in enumerate(crops) if c is not None]
            crops_detail = f"{crops_set}/{total_crops}" + (f" ({', '.join(set_crops)})" if set_crops else "")

            file_info_data.append({
                "File Name": file_name,
                "Size (MB)": f"{size_mb:.1f}",
                "Duration": duration_str,
                "Crops Set": crops_detail
            })

        st.dataframe(file_info_data, use_container_width=True, hide_index=True)

        selected_idx = st.sidebar.selectbox(
            "Choose a video:",
            range(len(temp_file_paths)),
            format_func=lambda i: os.path.basename(temp_file_paths[i])
        )

        selected_video_path = temp_file_paths[selected_idx]
        selected_video_name = os.path.basename(selected_video_path)

        st.sidebar.subheader("Crop Settings")

        if selected_video_name not in st.session_state.num_crops:
            st.session_state.num_crops[selected_video_name] = 1

        st.session_state.num_crops[selected_video_name] = st.sidebar.number_input(
            "Number of crops for this video",
            min_value=1,
            value=st.session_state.num_crops[selected_video_name],
            step=1,
            key=f"num_crops_{selected_video_name}"
        )

        num_crops = st.session_state.num_crops[selected_video_name]
        crop_index = st.sidebar.selectbox("Select crop index", range(num_crops), format_func=lambda x: f"Crop {x+1}")

        if selected_video_name not in st.session_state.crop_settings:
            st.session_state.crop_settings[selected_video_name] = [None] * num_crops
        elif len(st.session_state.crop_settings[selected_video_name]) < num_crops:
            current = st.session_state.crop_settings[selected_video_name]
            st.session_state.crop_settings[selected_video_name] = current + [None] * (num_crops - len(current))

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
            st.subheader(f"Draw Crop Box for Crop {crop_index + 1}")
            crop_box = st_cropper(
                st.session_state.frame_images[selected_video_name],
                realtime_update=True,
                box_color='#0000FF',
                aspect_ratio=None,
                return_type='box',
            )

            if st.button("Set Crop for This Video"):
                if crop_box and all(k in crop_box for k in ['left', 'top', 'width', 'height']):
                    crop_data = {
                        'x': int(round(crop_box['left'])),
                        'y': int(round(crop_box['top'])),
                        'w': int(round(crop_box['width'])),
                        'h': int(round(crop_box['height']))
                    }
                    st.session_state.crop_settings[selected_video_name][crop_index] = crop_data
                    st.success(f"Crop {crop_index + 1} set for {selected_video_name}")

        # Output settings
        st.sidebar.subheader("Output Settings")
        OUTPUT_DIR = st.sidebar.text_input("Folder name in Downloads", "Cropped_Videos")
        full_output_path = os.path.join(os.path.expanduser("~"), "Downloads", OUTPUT_DIR)
        os.makedirs(full_output_path, exist_ok=True)

        if st.sidebar.button("Crop All Videos"):
            st.session_state[f"frame_extracted_{selected_video_name}"] = False
            st.session_state["processing_started"] = True

            if not st.session_state.crop_settings:
                st.sidebar.warning("No crops have been set.")
            else:
                st.subheader("Cropping Process")

                for video_idx, video_path in enumerate(temp_file_paths):
                    video_name = os.path.basename(video_path)
                    crops = st.session_state.crop_settings.get(video_name, [])

                    for i, crop_data in enumerate(crops):
                        if not crop_data:
                            st.warning(f"Skipping {video_name} Crop {i + 1}: no crop defined.")
                            continue

                        output_file = os.path.join(full_output_path, f'{os.path.splitext(video_name)[0]}_crop{i+1}.mp4')

                        st.write(f"**{video_name} (Crop {i + 1})**")
                        st.write(f"Cropping to {crop_data['w']}x{crop_data['h']} at ({crop_data['x']}, {crop_data['y']})")

                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        status_text.info(f"Processing {video_name} Crop {i + 1}...")

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
                            status_text.success(f"Completed {video_name} Crop {i + 1}")

                        except Exception as e:
                            status_text.error(f"Error cropping {video_name} Crop {i + 1}: {str(e)}")

                        st.write("---")

                st.success(f"All finished! Cropped videos saved to: {full_output_path}")

    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
