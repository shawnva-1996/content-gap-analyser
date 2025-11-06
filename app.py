# This is the full code for: app.py

import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
import io
import csv
import yt_dlp
import os
import shutil
import zipfile
import plotly.express as px
from collections import Counter
import re

# --- Helper Functions ---

def convert_views_to_numeric(views_str):
    """
    Converts a view count string (e.g., "33.8K", "795.7M", "1234") into a numeric value.
    """
    views_str = str(views_str).strip()
    try:
        if 'K' in views_str:
            return int(float(views_str.replace('K', '')) * 1000)
        elif 'M' in views_str:
            return int(float(views_str.replace('M', '')) * 1000000)
        else:
            return int(views_str)
    except ValueError:
        return 0 # Return 0 if conversion fails

def parse_html_file(uploaded_file):
    """
    Parses a single uploaded TikTok HTML file and returns the extracted data.
    """
    video_data = []
    
    try:
        html_content = uploaded_file.read().decode('utf-8')
    except Exception as e:
        st.error(f"Error reading file {uploaded_file.name}: {e}")
        return []

    soup = BeautifulSoup(html_content, 'lxml')
    video_containers = soup.find_all('div', {'data-e2e': 'user-post-item'})

    if not video_containers:
        st.warning(f"No video posts found in {uploaded_file.name}.")
        return []

    for container in video_containers:
        try:
            link_tag = container.find('a')
            video_link = link_tag['href'] if link_tag and 'href' in link_tag.attrs else "N/A"
            
            # Extract profile name from URL
            profile_name = "N/A"
            if video_link != "N/A":
                try:
                    # Split URL: https://www.tiktok.com/@profilename/video/7569256496945548575
                    parts = video_link.split('/')
                    if len(parts) > 3 and parts[3].startswith('@'):
                        profile_name = parts[3]
                except Exception:
                    pass # Keep profile_name as "N/A"

            views_tag = container.find('strong', {'data-e2e': 'video-views'})
            views = views_tag.text if views_tag else "0"

            img_tag = container.find('img')
            caption = img_tag.get('alt', 'N/A') if img_tag else "N/A"

            video_data.append([video_link, profile_name, views, caption])

        except Exception as e:
            st.error(f"Error parsing a video item in {uploaded_file.name}: {e}")
            video_data.append(["PARSE_ERROR", "N/A", "N/A", str(e)])

    return video_data

def download_videos_and_zip(video_links, zip_file_name):
    """
    Handles downloading videos, zipping them in memory, and returning the zip.
    Returns (zip_buffer, status_message)
    """
    if not video_links:
        st.warning("No videos match the criteria.")
        return None
    
    download_dir = f"temp_download_{zip_file_name.split('.')[0]}"
    if os.path.exists(download_dir):
        shutil.rmtree(download_dir)
    os.makedirs(download_dir)

    try:
        # --- Download ---
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': os.path.join(download_dir, '%(id)s - %(title).50s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'merge_output_format': 'mp4',
            'ignoreerrors': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download(video_links)
        except yt_dlp.utils.DownloadError as e:
            st.error(f"A download error occurred: {e}")
        except Exception as e:
            st.error(f"An unexpected error occurred with yt-dlp: {e}")
            raise # Re-raise to be caught by the button's try...except

        # --- Zip ---
        st.spinner("Zipping files...")
        memory_zip = io.BytesIO()
        with zipfile.ZipFile(memory_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            found_files = False
            for root, _, files in os.walk(download_dir):
                for file in files:
                    found_files = True
                    file_path = os.path.join(root, file)
                    zf.write(file_path, arcname=os.path.relpath(file_path, download_dir))
            
            if not found_files:
                st.warning("No files were successfully downloaded to zip.")
                return None

        memory_zip.seek(0)
        return memory_zip

    except Exception as e:
        st.error(f"An error occurred during zipping: {e}")
        return None
    finally:
        # Clean up
        if os.path.exists(download_dir):
            shutil.rmtree(download_dir)

@st.cache_data
def convert_df_to_csv(dataframe):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(dataframe.columns) # Write header
    for index, row in dataframe.iterrows():
        writer.writerow(row)
    return output.getvalue()

def get_common_topics(captions_series, top_n=20):
    """
    Extracts common words from a pandas Series of captions.
    """
    # Basic stop words list, expanded for TikTok context
    stop_words = set([
        'a', 'an', 'the', 'is', 'in', 'of', 'to', 'by', 'with', 'and', 'created', 
        'original', 'sound', 's', 't', 'm', 'for', 'on', 'it', 'its', 'this', 
        'that', 'be', 'at', 'with', 'my', 'you', 'your', 'https', 'www', 'tiktok', 
        'com', 'video', 'i', 'me', 'he', 'she', 'they', 'we', 'are', 'was', 'were',
        'not', 'but', 'so', 'up', 'out', 'if', 'all', 'new', 'get', 'just', 'like'
    ])

    all_captions_text = ' '.join(captions_series.astype(str)).lower()
    
    # Find all words (alphanumeric sequences)
    words = re.findall(r'\b[a-zA-Z0-9]+\b', all_captions_text)
    
    # Filter out stop words and short words
    filtered_words = [
        word for word in words 
        if word not in stop_words and len(word) > 2
    ]
    
    # Get the most common words
    topic_counts = Counter(filtered_words).most_common(top_n)
    
    if not topic_counts:
        return pd.DataFrame(columns=['Topic', 'Frequency'])
        
    return pd.DataFrame(topic_counts, columns=['Topic', 'Frequency'])


# --- Streamlit App UI ---

st.set_page_config(layout="wide")
st.title("🎬 Viz Alliance TikTok HTML Processor & Downloader")
st.write("Upload `.html` files, view data, analyze viral content, and download videos.")

# 1. File Uploader
uploaded_files = st.file_uploader(
    "Upload your saved .html files",
    type=['html', 'htm'],
    accept_multiple_files=True
)

if uploaded_files:
    with st.spinner("Processing files..."):
        all_video_data = []
        for file in uploaded_files:
            st.write(f"Processing `{file.name}`...")
            data = parse_html_file(file)
            all_video_data.extend(data)
    
    if all_video_data:
        st.success(f"Successfully processed {len(uploaded_files)} files and found {len(all_video_data)} total videos!")

        # 2. Create and Display DataFrame
        df = pd.DataFrame(all_video_data, columns=['Video Link', 'Profile Name', 'Views', 'Caption'])
        df['Numeric Views'] = df['Views'].apply(convert_views_to_numeric)
        df = df[['Video Link', 'Profile Name', 'Views', 'Numeric Views', 'Caption']] # Reorder

        st.subheader("Combined Video Data")
        st.write("Click headers to sort. Select rows (shift-click) to enable 'Download Selected'.")
        
        st.dataframe(
            df, 
            key="video_selection", 
            on_select="rerun", 
            selection_mode="multi-row",
            use_container_width=True,
            hide_index=True
        )

        # 3. Download CSV Button
        csv_data = convert_df_to_csv(df)
        st.download_button(
            label="⬇️ Download Combined CSV",
            data=csv_data,
            file_name="tiktok_videos_combined.csv",
            mime="text/csv",
        )

        # 4. Viral Video Analysis
        st.subheader("📈 Viral Video Analysis")
        
        # Define "viral"
        top_n = st.slider("Select 'Top N' videos to analyze:", 
                          min_value=5, 
                          max_value=min(100, len(df)), # Cap at 100 or df length
                          value=min(20, len(df)), # Default to 20 or df length
                          step=5)

        viral_df = df.sort_values(by='Numeric Views', ascending=False).head(top_n)

        if not viral_df.empty:
            viz_col1, viz_col2 = st.columns(2)
            
            with viz_col1:
                # --- Viz 1: Distribution by Profile ---
                st.write(f"**Top {top_n} Videos by Profile**")
                profile_views = viral_df.groupby('Profile Name')['Numeric Views'].sum().reset_index()
                profile_views = profile_views.sort_values(by='Numeric Views', ascending=False)
                
                fig1 = px.bar(
                    profile_views,
                    x='Profile Name',
                    y='Numeric Views',
                    color='Profile Name',
                    title=f"Total Views from Top {top_n} Videos, by Profile",
                    hover_data=['Profile Name', 'Numeric Views']
                )
                fig1.update_layout(xaxis_title="Profile", yaxis_title="Total Views", showlegend=False)
                st.plotly_chart(fig1, use_container_width=True)

            with viz_col2:
                # --- Viz 2: Common Topics ---
                st.write(f"**Top {top_n} Video Topics**")
                topic_df = get_common_topics(viral_df['Caption'], top_n=20)
                
                if not topic_df.empty:
                    fig2 = px.bar(
                        topic_df,
                        x='Topic',
                        y='Frequency',
                        color='Topic',
                        title=f"Most Common Words in Top {top_n} Video Captions",
                        hover_data=['Topic', 'Frequency']
                    )
                    fig2.update_layout(xaxis_title="Word/Topic", yaxis_title="Frequency", showlegend=False)
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("No common topics found in captions (or captions are missing).")
        else:
            st.warning("Not enough data to display visualizations.")


        # 5. Download Videos Section
        st.subheader("⬇️ Download Videos")
        st.info("Note: Video downloading requires `yt-dlp` and `ffmpeg` to be installed on the server hosting this app.")

        # --- Download by Views ---
        st.write("**Download by View Count**")
        min_views = st.number_input("Enter minimum view count:", 
                                    min_value=0, 
                                    value=100000, 
                                    step=1000)
        
        if st.button(f"Download Videos with ≥ {min_views:,} Views", use_container_width=True):
            filtered_df = df[df['Numeric Views'] >= min_views]
            links_to_download = filtered_df['Video Link'].tolist()
            
            with st.spinner(f"Downloading {len(links_to_download)} video(s)... This may take a while."):
                zip_buffer = download_videos_and_zip(links_to_download, "tiktok_videos_min_views.zip")
                
                if zip_buffer:
                    st.download_button(
                        label=f"⬇️ Click to Download ({len(links_to_download)} videos) as ZIP",
                        data=zip_buffer,
                        file_name="tiktok_videos_min_views.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
                    st.success("Zip file ready!")
        
        st.divider()

        # --- Download Selected / All ---
        dl_col1, dl_col2 = st.columns(2)
        selection_state = st.session_state.get("video_selection", {})
        selected_indices = selection_state.get("selection", {}).get("rows", [])

        with dl_col1:
            # --- Download Selected Videos ---
            if st.button(f"Download {len(selected_indices)} Selected Videos", disabled=not selected_indices, use_container_width=True):
                selected_df = df.iloc[selected_indices]
                links_to_download = selected_df['Video Link'].tolist()
                
                with st.spinner(f"Downloading {len(links_to_download)} video(s)..."):
                    zip_buffer = download_videos_and_zip(links_to_download, "tiktok_videos_selected.zip")
                    
                    if zip_buffer:
                        st.download_button(
                            label="⬇️ Click to Download Selected as ZIP",
                            data=zip_buffer,
                            file_name="tiktok_videos_selected.zip",
                            mime="application/zip",
                            use_container_width=True
                        )
                        st.success("Zip file ready!")

        with dl_col2:
            # --- Download All Videos ---
            if st.button(f"Download All {len(df)} Videos", use_container_width=True):
                links_to_download = df['Video Link'].tolist()
                
                with st.spinner(f"Downloading all {len(links_to_download)} videos... This will take a while."):
                    zip_buffer = download_videos_and_zip(links_to_download, "tiktok_videos_all.zip")
                    
                    if zip_buffer:
                        st.download_button(
                            label="⬇️ Click to Download All as ZIP",
                            data=zip_buffer,
                            file_name="tiktok_videos_all.zip",
                            mime="application/zip",
                            use_container_width=True
                        )
                        st.success("Zip file ready!")

    else:
        st.warning("No video data could be extracted from the uploaded file(s).")
else:
    st.info("Upload your HTML files to begin.")