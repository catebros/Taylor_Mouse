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
    
        st.info("Cropped videos will be saved to your Downloads folder")
        
        st.subheader("Select Video for Crop Area")
        video_names = [os.path.basename(path) for path in temp_file_paths]
        selected_video_idx = st.selectbox("Choose a video to set crop area:", range(len(video_names)), format_func=lambda x: video_names[x])
        selected_video_path = temp_file_paths[selected_video_idx]
        
        st.subheader("Extract Frame for Cropping")
        
        probe = ffmpeg.probe(selected_video_path)
        duration = float(probe['format']['duration'])
        
        frame_time = st.slider("Select time to extract frame (seconds)", 
                              min_value=0.0, 
                              max_value=duration, 
                              value=duration/2, 
                              step=0.1)
        
        if st.button("Extract Frame", type="secondary"):
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
        
        if hasattr(st.session_state, 'frame_extracted') and st.session_state.frame_extracted:
            st.subheader("Select Crop Area")
            st.write("Draw a rectangle on the image to select the area you want to keep in all videos.")
            
            cropped_img = st_cropper(
                st.session_state.frame_image, 
                realtime_update=True, 
                box_color='#0000FF',
                aspect_ratio=None,
                return_type='box'
            )

            #TODO review starting from here
            
            if cropped_img:
                original_width, original_height = st.session_state.frame_image.size
                
                if hasattr(cropped_img, 'left'):
                    x_start = int(cropped_img.left)
                    y_start = int(cropped_img.top)
                    x_end = int(cropped_img.left + cropped_img.width)
                    y_end = int(cropped_img.top + cropped_img.height)
                    crop_width = int(cropped_img.width)
                    crop_height = int(cropped_img.height)
                else:
                    x_start = 0
                    y_start = 0
                    crop_width = min(640, original_width)
                    crop_height = min(480, original_height)


                # Perform pixel validation for the offset, we know the
                
                st.sidebar.header('Crop Settings')
                st.sidebar.write(f"**Selected area:** {crop_width} x {crop_height}")
                st.sidebar.write(f"**Original dimensions:** {original_width} x {original_height}")
                st.sidebar.write(f"**Position:** ({x_start}, {y_start})")

                manual_width = st.sidebar.number_input("Crop Width", min_value=100, max_value=original_width, value=crop_width, step=10)
                manual_height = st.sidebar.number_input("Crop Height", min_value=100, max_value=original_height, value=crop_height, step=10)
                x_offset = st.sidebar.number_input("X Offset", min_value=0, max_value=max(0, original_width-manual_width), value=x_start, step=10)
                y_offset = st.sidebar.number_input("Y Offset", min_value=0, max_value=max(0, original_height-manual_height), value=y_start, step=10)
                
# ----------------------This works--------------------------------------------------------------

                if x_offset + manual_width > original_width:
                    st.sidebar.error("Crop area exceeds video width!")
                    manual_width = original_width - x_offset
                    
                if y_offset + manual_height > original_height:
                    st.sidebar.error("Crop area exceeds video height!")
                    manual_height = original_height - y_offset
                
                st.sidebar.header('Output Settings')
                OUTPUT_DIR = st.sidebar.text_input("Folder name in Downloads", "Cropped_Videos")
                full_output_path = os.path.join(downloads_path, OUTPUT_DIR)
                os.makedirs(full_output_path, exist_ok=True)
                
                st.sidebar.info(f"Videos will be saved to: Downloads/{OUTPUT_DIR}")
                
                st.sidebar.subheader("Crop Preview")
                st.sidebar.write(f"Final size: {manual_width} x {manual_height}")
                st.sidebar.write(f"Position: ({x_offset}, {y_offset})")

                if st.sidebar.button("Start Cropping Videos", type="primary"):
                    st.subheader("Cropping Process")
                    
                    for video_idx, video_path in enumerate(temp_file_paths):
                        video_name = os.path.splitext(os.path.basename(video_path))[0]
                        output_file = os.path.join(full_output_path, f'{video_name}_cropped.mp4')
                        
                        st.write(f"**Video {video_idx + 1}/{len(temp_file_paths)}: {video_name}**")
                        st.write(f"Cropping to {manual_width}x{manual_height} at position ({x_offset}, {y_offset})")
                        
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        status_text.info(f"Processing {video_name}...")
                        
                        try:
                            crop_filter = f"crop={manual_width}:{manual_height}:{x_offset}:{y_offset}"
                            
                            (
                                ffmpeg
                                .input(video_path)
                                .filter('crop', manual_width, manual_height, x_offset, y_offset)
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
            st.info("Please extract a frame first to select the crop area.")
 
    except Exception as e:
        st.error(f"Error processing videos: {str(e)}")