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
        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")

        st.sidebar.subheader("Select Video for Crop Area")
        video_names = [os.path.basename(path) for path in temp_file_paths]
        selected_video_idx = st.sidebar.selectbox("Choose a video:", range(len(video_names)), format_func=lambda x: video_names[x])
        selected_video_path = temp_file_paths[selected_video_idx]

        st.sidebar.subheader("Extract Frame for Cropping")

        probe = ffmpeg.probe(selected_video_path)
        duration = float(probe['format']['duration'])

        frame_time = st.sidebar.slider("Select time (seconds)",
                                        min_value=0.0,
                                        max_value=duration,
                                        value=duration/2,
                                        step=0.1)

        if st.sidebar.button("Extract Frame", type="primary"):
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
                st.session_state.frame_image = frame_image.copy()
                st.session_state.frame_extracted = True

                frame_image.close()

            except Exception as e:
                st.error(f"Error extracting frame: {str(e)}")
            finally:
                try:
                    if os.path.exists(temp_frame_path):
                        os.unlink(temp_frame_path)
                except:
                    pass

        if st.session_state.get('frame_extracted', False):
            st.subheader("Draw Crop Box")

            crop_box = st_cropper(
                st.session_state.frame_image,
                realtime_update=True,
                box_color='#0000FF',
                aspect_ratio=None,
                return_type='box',
            )


            st.sidebar.header('Output Settings')
            OUTPUT_DIR = st.sidebar.text_input("Folder name in Downloads", "Cropped_Videos")
            full_output_path = os.path.join(downloads_path, OUTPUT_DIR)
            os.makedirs(full_output_path, exist_ok=True)

            if st.sidebar.button("Start Cropping Videos", type="primary"):
                if crop_box and all(k in crop_box for k in ['left', 'top', 'width', 'height']):
                    x_offset = int(round(crop_box['left']))
                    y_offset = int(round(crop_box['top']))
                    crop_width = int(round(crop_box['width']))
                    crop_height = int(round(crop_box['height']))

                    st.subheader("Cropping Process")

                    for video_idx, video_path in enumerate(temp_file_paths):
                        video_name = os.path.splitext(os.path.basename(video_path))[0]
                        output_file = os.path.join(full_output_path, f'{video_name}_cropped.mp4')

                        st.write(f"**Video {video_idx + 1}/{len(temp_file_paths)}: {video_name}**")

                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        status_text.info(f"Processing {video_name}...")

                        try:
                            (
                                ffmpeg
                                .input(video_path)
                                .filter('crop', crop_width, crop_height, x_offset, y_offset)
                                .output(output_file, vcodec='libx264', acodec='aac')
                                .overwrite_output()
                                .run(quiet=True)
                            )

                            progress_bar.progress(1.0)
                            status_text.success(f"Completed {video_name}")

                        except Exception as e:
                            status_text.error(f"Error cropping {video_name}: {str(e)}")

                        st.write("---")

                    st.success(f"All videos cropped successfully! Check your Downloads folder: {full_output_path}")
                else:
                    st.sidebar.error("No valid crop box. Please draw one before clicking.")
        else:
            st.info("Please extract a frame first to select the crop area.")

    except Exception as e:
        st.error(f"Error processing videos: {str(e)}")
