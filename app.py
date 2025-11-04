import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
import io
import csv

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
    This is adapted from your original extract_data_from_html function.
    """
    video_data = []
    
    # Read content from the uploaded file object
    try:
        html_content = uploaded_file.read().decode('utf-8')
    except Exception as e:
        st.error(f"Error reading file {uploaded_file.name}: {e}")
        return []

    soup = BeautifulSoup(html_content, 'lxml')

    # Find all video post containers using the data-e2e attribute
    video_containers = soup.find_all('div', {'data-e2e': 'user-post-item'})

    if not video_containers:
        st.warning(f"No video posts found in {uploaded_file.name}.")
        return []

    # Loop through each container and extract the required data
    for container in video_containers:
        try:
            # Extract the video link
            link_tag = container.find('a')
            video_link = link_tag['href'] if link_tag and 'href' in link_tag.attrs else "N/A"

            # Extract the view count
            views_tag = container.find('strong', {'data-e2e': 'video-views'})
            views = views_tag.text if views_tag else "0"

            # Extract the caption
            # Find the <img> tag within the container and get its 'alt' text
            img_tag = container.find('img')
            caption = img_tag.get('alt', 'N/A') if img_tag else "N/A"

            video_data.append([video_link, views, caption])

        except Exception as e:
            st.error(f"Error parsing a video item in {uploaded_file.name}: {e}")
            video_data.append(["PARSE_ERROR", "N/A", str(e)])

    return video_data

# --- Streamlit App UI ---

st.set_page_config(layout="wide")
st.title("🎬 TikTok HTML File Processor")
st.write("Upload one or more TikTok profile `.html` files you've saved to your computer. The app will combine them, let you view the data, and provide a download link.")

# 1. File Uploader
uploaded_files = st.file_uploader(
    "Upload your saved .html files",
    type=['html', 'htm'],
    accept_multiple_files=True
)

all_video_data = []
if uploaded_files:
    with st.spinner("Processing files..."):
        for file in uploaded_files:
            st.write(f"Processing `{file.name}`...")
            data = parse_html_file(file)
            all_video_data.extend(data)
    
    if all_video_data:
        st.success(f"Successfully processed {len(uploaded_files)} files and found {len(all_video_data)} total videos!")

        # 2. Create and Display DataFrame (Viewable & Sortable)
        df = pd.DataFrame(all_video_data, columns=['Video Link', 'Views', 'Caption'])
        
        # 3. Create numeric views column for sorting
        df['Numeric Views'] = df['Views'].apply(convert_views_to_numeric)
        
        # Reorder columns to be more logical
        df = df[['Video Link', 'Views', 'Numeric Views', 'Caption']]

        st.subheader("Combined Video Data")
        st.write("Click any column header (especially 'Numeric Views') to sort.")
        st.dataframe(df)

        # 4. Download Button
        @st.cache_data
        def convert_df_to_csv(dataframe):
            # Use io.StringIO to create a text-based in-memory file
            output = io.StringIO()
            # Use csv.writer to handle any special characters in captions
            writer = csv.writer(output)
            writer.writerow(dataframe.columns) # Write header
            for index, row in dataframe.iterrows():
                writer.writerow(row)
            return output.getvalue()

        csv_data = convert_df_to_csv(df)

        st.download_button(
            label="⬇️ Download Combined CSV",
            data=csv_data,
            file_name="tiktok_videos_combined.csv",
            mime="text/csv",
        )
    else:
        st.warning("No video data could be extracted from the uploaded file(s).")

else:
    st.info("Upload your HTML files to begin.")

